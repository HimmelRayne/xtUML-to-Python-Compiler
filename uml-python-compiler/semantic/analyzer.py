"""Semantic analyzer: validates the AST and fills the symbol table.

All errors are collected (not just the first) and returned sorted by position.
"""

import keyword

from errors.errors import SemanticError
from semantic.symbol_table import BUILTIN_TYPES, SymbolTable

# names the generated code relies on: a user class with this name would shadow them
RESERVED_CLASS_NAMES = BUILTIN_TYPES + ("ABC", "abstractmethod")


class SemanticAnalyzer:
    def __init__(self):
        self.symbols = SymbolTable()
        self.errors = []

    def _error(self, message, pos):
        self.errors.append(SemanticError(message, pos[0], pos[1]))

    # ---- entry point ---------------------------------------------
    def analyze(self, program):
        self.symbols = SymbolTable()
        self.errors = []

        for node in program.classes:          # pass 1: declare names
            self._declare(node)
        for symbol in self.symbols.classes.values():   # pass 2: check each class
            self._check_header(symbol.node)
            self._check_members(symbol)
        for rel in program.relationships:     # pass 3: relationships
            self._check_relationship(rel)
        self._check_cycles()                  # pass 4: circular inheritance

        self.errors.sort(key=lambda e: (e.line, e.column))
        return self.errors

    def _check_name(self, name, pos, what):
        """Names that are Python keywords (or 'self') would produce invalid Python."""
        if keyword.iskeyword(name) or name == "self":
            self._error(f"{what} name '{name}' is a reserved Python word.", pos)

    # ---- pass 1 --------------------------------------------------
    def _declare(self, node):
        self._check_name(node.name, (node.line, node.column), "Class")
        if node.name in RESERVED_CLASS_NAMES:
            self._error(f"Class name '{node.name}' is reserved (built-in type or "
                        f"used by the generated code).", (node.line, node.column))
        existing = self.symbols.define(node)
        if existing:
            self._error(f"Class '{node.name}' is already defined "
                        f"(first defined at line {existing.node.line})",
                        (node.line, node.column))

    # ---- pass 2: inheritance / implements ------------------------
    def _check_header(self, node):
        if node.parent:
            parent = self.symbols.lookup(node.parent)
            if parent is None:
                self._error(f"Class '{node.parent}' is not defined.", node.parent_pos)
            elif node.kind == "class" and parent.node.kind == "interface":
                self._error(f"Class '{node.name}' cannot extend interface "
                            f"'{node.parent}'; use 'implements' instead.", node.parent_pos)
            elif node.kind == "interface" and parent.node.kind == "class":
                self._error(f"Interface '{node.name}' cannot extend class "
                            f"'{node.parent}'.", node.parent_pos)

        if node.interfaces and node.kind == "interface":
            self._error(f"Interface '{node.name}' cannot use 'implements'; "
                        f"use 'extends' instead.", node.interface_pos[0])
            return
        for name, pos in zip(node.interfaces, node.interface_pos):
            target = self.symbols.lookup(name)
            if target is None:
                self._error(f"Interface '{name}' is not defined.", pos)
            elif target.node.kind != "interface":
                self._error(f"'{name}' is a class, not an interface; "
                            f"use 'extends' to inherit from it.", pos)

    # ---- pass 2: members -----------------------------------------
    def _check_members(self, symbol):
        node = symbol.node

        for attr in node.attributes:
            pos = (attr.line, attr.column)
            self._check_name(attr.name, pos, "Attribute")
            if node.kind == "interface":
                self._error(f"Interface '{node.name}' cannot declare attributes "
                            f"('{attr.name}').", pos)
            if attr.name in symbol.attributes:
                self._error(f"Duplicate attribute '{attr.name}' in class '{node.name}'.", pos)
            else:
                symbol.attributes[attr.name] = attr
            self._check_type(attr.type, attr.type_pos, False, f"attribute '{attr.name}'")

        for method in node.methods:
            pos = (method.line, method.column)
            self._check_name(method.name, pos, "Method")
            if method.name in symbol.attributes:
                self._error(f"'{method.name}' is declared as both an attribute and "
                            f"a method in class '{node.name}'.", pos)
            if method.name in symbol.methods:
                self._error(f"Duplicate method '{method.name}' in class '{node.name}' "
                            f"(overloading is not supported).", pos)
            else:
                symbol.methods[method.name] = method

            seen = set()
            for param in method.parameters:
                if param.name in seen:
                    self._error(f"Duplicate parameter '{param.name}' in method "
                                f"'{method.name}'.", (param.line, param.column))
                self._check_name(param.name, (param.line, param.column), "Parameter")
                seen.add(param.name)
                self._check_type(param.type, param.type_pos, False,
                                 f"parameter '{param.name}'")
            self._check_type(method.return_type, method.return_type_pos, True,
                             f"method '{method.name}'")

    def _check_type(self, type_name, pos, allow_void, context):
        if type_name == "void":
            if not allow_void:
                self._error(f"'void' cannot be used as the type of {context}.", pos)
        elif not self.symbols.is_known_type(type_name):
            self._error(f"Unknown type '{type_name}'. Use a built-in type "
                        f"({', '.join(BUILTIN_TYPES)}) or a declared class.", pos)

    # ---- pass 3: relationships -----------------------------------
    def _check_relationship(self, rel):
        source = self.symbols.lookup(rel.source)
        if source is None:
            self._error(f"Class '{rel.source}' is not defined.", rel.source_pos)
        elif source.node.kind == "interface":
            self._error(f"Interface '{rel.source}' cannot be the source of an "
                        f"association.", rel.source_pos)
        if rel.name:
            self._check_name(rel.name, (rel.line, rel.column), "Relationship")
        if self.symbols.lookup(rel.target) is None:
            self._error(f"Class '{rel.target}' is not defined.", rel.target_pos)

    # ---- pass 4: circular inheritance ----------------------------
    def _check_cycles(self):
        reported = set()
        for symbol in self.symbols.classes.values():
            start = symbol.node.name
            if start in reported:
                continue
            path = [start]
            current = symbol.node.parent
            while current is not None:
                if current == start:
                    self._error("Circular inheritance detected: "
                                + " -> ".join(path + [start]),
                                (symbol.node.line, symbol.node.column))
                    reported.update(path)
                    break
                target = self.symbols.lookup(current)
                if current in path or target is None:
                    break  # a cycle not containing 'start' is reported for its own members
                path.append(current)
                current = target.node.parent
