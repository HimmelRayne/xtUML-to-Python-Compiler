"""Recursive descent parser: tokens -> AST (see grammar in README)."""

import re

from errors.errors import ParserError
from lexer import TokenType as T
from uml_ast.nodes import (AttributeNode, ClassNode, MethodNode, ParameterNode,
                           Program, RelationshipNode)

VISIBILITY = {T.PLUS: "public", T.MINUS: "private", T.HASH: "protected"}

# "1", "*", "0..1", "1..*", "2..5"  (lower bound of a range must be a number)
MULTIPLICITY_RE = re.compile(r"^(?:\d+|\*)$|^(\d+)\.\.(?:(\d+)|\*)$")


class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    # ---- helpers -------------------------------------------------
    def _current(self):
        return self.tokens[self.pos]

    def _advance(self):
        tok = self.tokens[self.pos]
        if tok.type != T.EOF:
            self.pos += 1
        return tok

    def _check(self, *types):
        return self._current().type in types

    def _match(self, *types):
        """Consume and return the token if it has one of the types, else None."""
        return self._advance() if self._check(*types) else None

    def _error(self, expected, tok=None):
        tok = tok or self._current()
        found = "end of file" if tok.type == T.EOF else repr(tok.value)
        return ParserError(f"Expected {expected}, found {found}", tok.line, tok.column)

    def _expect(self, ttype, expected):
        if not self._check(ttype):
            raise self._error(expected)
        return self._advance()

    # ---- program -------------------------------------------------
    def parse(self):
        program = Program()
        while not self._check(T.EOF):
            if self._check(T.ABSTRACT, T.CLASS, T.INTERFACE):
                program.classes.append(self._class_decl())
            elif self._check(T.IDENTIFIER):
                program.relationships.append(self._relationship())
            else:
                raise self._error("'class', 'interface' or a relationship")
        return program

    # ---- class / interface ---------------------------------------
    def _class_decl(self):
        abstract_tok = self._match(T.ABSTRACT)
        if self._check(T.INTERFACE) and abstract_tok:
            raise ParserError("An interface cannot be 'abstract'",
                              abstract_tok.line, abstract_tok.column)
        if not self._check(T.CLASS, T.INTERFACE):
            raise self._error("'class' or 'interface'")
        kind = self._advance().value
        name_tok = self._expect(T.IDENTIFIER, "a name")

        node = ClassNode(name=name_tok.value, kind=kind,
                         modifier="abstract" if abstract_tok else None,
                         line=name_tok.line, column=name_tok.column)

        if self._match(T.EXTENDS):
            parent = self._expect(T.IDENTIFIER, "a parent name after 'extends'")
            node.parent = parent.value
            node.parent_pos = (parent.line, parent.column)

        if self._match(T.IMPLEMENTS):
            while True:
                tok = self._expect(T.IDENTIFIER, "an interface name after 'implements'")
                node.interfaces.append(tok.value)
                node.interface_pos.append((tok.line, tok.column))
                if not self._match(T.COMMA):
                    break

        self._expect(T.LBRACE, "'{'")
        while not self._check(T.RBRACE):
            if self._check(T.EOF):
                raise self._error("'}' to close the class")
            self._member(node)
        self._expect(T.RBRACE, "'}'")
        return node

    # ---- members -------------------------------------------------
    def _member(self, cls):
        visibility = "public"
        vis_tok = self._match(T.PLUS, T.MINUS, T.HASH)
        if vis_tok:
            visibility = VISIBILITY[vis_tok.type]

        name_tok = self._expect(T.IDENTIFIER, "a member name")
        if self._check(T.COLON):
            cls.attributes.append(self._attribute(name_tok, visibility))
        elif self._check(T.LPAREN):
            cls.methods.append(self._method(name_tok, visibility))
        else:
            raise self._error("':' (attribute) or '(' (method)")

    def _attribute(self, name_tok, visibility):
        self._expect(T.COLON, "':'")
        type_tok = self._expect(T.IDENTIFIER, "a type")
        return AttributeNode(name_tok.value, type_tok.value, visibility,
                             (type_tok.line, type_tok.column),
                             name_tok.line, name_tok.column)

    def _method(self, name_tok, visibility):
        self._expect(T.LPAREN, "'('")
        params = []
        if not self._check(T.RPAREN):
            while True:
                params.append(self._parameter())
                if not self._match(T.COMMA):
                    break
        self._expect(T.RPAREN, "')'")

        return_type, return_pos = "void", (name_tok.line, name_tok.column)
        if self._match(T.COLON):
            type_tok = self._expect(T.IDENTIFIER, "a return type")
            return_type, return_pos = type_tok.value, (type_tok.line, type_tok.column)
        return MethodNode(name_tok.value, params, return_type, visibility,
                          return_pos, name_tok.line, name_tok.column)

    def _parameter(self):
        name_tok = self._expect(T.IDENTIFIER, "a parameter name")
        self._expect(T.COLON, "':' after parameter name")
        type_tok = self._expect(T.IDENTIFIER, "a parameter type")
        return ParameterNode(name_tok.value, type_tok.value,
                             (type_tok.line, type_tok.column),
                             name_tok.line, name_tok.column)

    # ---- relationship --------------------------------------------
    def _relationship(self):
        src = self._expect(T.IDENTIFIER, "a class name")
        src_mult = self._multiplicity()
        self._expect(T.ARROW, "'-->'")
        tgt_mult = self._multiplicity()
        tgt = self._expect(T.IDENTIFIER, "a class name after '-->'")
        name = None
        if self._match(T.COLON):
            name = self._expect(T.IDENTIFIER, "a relationship name").value
        return RelationshipNode(
            source=src.value, target=tgt.value,
            source_multiplicity=src_mult, target_multiplicity=tgt_mult,
            name=name,
            source_pos=(src.line, src.column), target_pos=(tgt.line, tgt.column),
            line=src.line, column=src.column)

    def _multiplicity(self):
        tok = self._match(T.STRING)
        if tok is None:
            return None
        m = MULTIPLICITY_RE.match(tok.value)
        if not m or (m.group(2) and int(m.group(1)) > int(m.group(2))):
            raise ParserError(
                f'Invalid multiplicity "{tok.value}" (expected e.g. "1", "*", "0..1", "1..*")',
                tok.line, tok.column)
        return tok.value
