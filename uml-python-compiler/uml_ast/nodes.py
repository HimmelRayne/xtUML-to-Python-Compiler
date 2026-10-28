"""AST node definitions. Every node keeps its source position for error messages.

Positions of *references* to other names (parent, types, relationship ends)
are stored as (line, column) tuples so the semantic analyzer can point at them.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

Pos = Tuple[int, int]  # (line, column)


@dataclass
class ParameterNode:
    name: str
    type: str
    type_pos: Pos = (0, 0)
    line: int = 0
    column: int = 0


@dataclass
class AttributeNode:
    name: str
    type: str
    visibility: str = "public"  # public | private | protected
    type_pos: Pos = (0, 0)
    line: int = 0
    column: int = 0


@dataclass
class MethodNode:
    name: str
    parameters: List[ParameterNode] = field(default_factory=list)
    return_type: str = "void"
    visibility: str = "public"
    return_type_pos: Pos = (0, 0)
    line: int = 0
    column: int = 0


@dataclass
class ClassNode:
    name: str
    kind: str = "class"  # class | interface
    modifier: Optional[str] = None  # "abstract" or None
    parent: Optional[str] = None
    parent_pos: Pos = (0, 0)
    interfaces: List[str] = field(default_factory=list)
    interface_pos: List[Pos] = field(default_factory=list)
    attributes: List[AttributeNode] = field(default_factory=list)
    methods: List[MethodNode] = field(default_factory=list)
    line: int = 0
    column: int = 0


@dataclass
class RelationshipNode:
    source: str
    target: str
    source_multiplicity: Optional[str] = None
    target_multiplicity: Optional[str] = None
    relationship_type: str = "association"
    name: Optional[str] = None
    source_pos: Pos = (0, 0)
    target_pos: Pos = (0, 0)
    line: int = 0
    column: int = 0


@dataclass
class Program:
    classes: List[ClassNode] = field(default_factory=list)
    relationships: List[RelationshipNode] = field(default_factory=list)
