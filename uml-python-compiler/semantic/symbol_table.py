"""Symbol table: remembers every declared class and its members."""

from dataclasses import dataclass, field
from typing import Dict, Optional

from uml_ast.nodes import AttributeNode, ClassNode, MethodNode

BUILTIN_TYPES = ("int", "float", "str", "string", "bool", "void")


@dataclass
class ClassSymbol:
    node: ClassNode
    attributes: Dict[str, AttributeNode] = field(default_factory=dict)
    methods: Dict[str, MethodNode] = field(default_factory=dict)


class SymbolTable:
    def __init__(self):
        self.classes: Dict[str, ClassSymbol] = {}

    def define(self, node: ClassNode) -> Optional[ClassSymbol]:
        """Register a class. Returns the existing symbol if the name is taken."""
        if node.name in self.classes:
            return self.classes[node.name]
        self.classes[node.name] = ClassSymbol(node)
        return None

    def lookup(self, name: str) -> Optional[ClassSymbol]:
        return self.classes.get(name)

    def is_known_type(self, name: str) -> bool:
        return name in BUILTIN_TYPES or name in self.classes
