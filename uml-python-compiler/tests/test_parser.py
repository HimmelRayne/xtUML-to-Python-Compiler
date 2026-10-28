import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from errors.errors import ParserError
from lexer import Lexer
from uml_parser import Parser


def parse(src):
    return Parser(Lexer(src).tokenize()).parse()


class TestParser(unittest.TestCase):
    def test_empty_class(self):
        prog = parse("class A { }")
        self.assertEqual(len(prog.classes), 1)
        c = prog.classes[0]
        self.assertEqual((c.name, c.kind, c.modifier, c.parent), ("A", "class", None, None))
        self.assertEqual((c.attributes, c.methods), ([], []))

    def test_attributes_and_visibility(self):
        c = parse("class A { - id: int + name: str # email: str age: int }").classes[0]
        self.assertEqual([(a.name, a.type, a.visibility) for a in c.attributes],
                         [("id", "int", "private"), ("name", "str", "public"),
                          ("email", "str", "protected"), ("age", "int", "public")])

    def test_methods(self):
        c = parse("class A { + login(): bool - run() }").classes[0]
        self.assertEqual([(m.name, m.return_type, m.visibility) for m in c.methods],
                         [("login", "bool", "public"), ("run", "void", "private")])

    def test_method_parameters(self):
        m = parse("class A { + f(a: int, b: str): bool }").classes[0].methods[0]
        self.assertEqual([(p.name, p.type) for p in m.parameters], [("a", "int"), ("b", "str")])

    def test_inheritance(self):
        c = parse("class B extends A { }").classes[0]
        self.assertEqual(c.parent, "A")
        self.assertEqual(c.parent_pos, (1, 17))

    def test_abstract_class_and_interface(self):
        prog = parse("abstract class A { } interface I { + f(): void }")
        self.assertEqual(prog.classes[0].modifier, "abstract")
        self.assertEqual(prog.classes[1].kind, "interface")

    def test_implements(self):
        c = parse("class A implements I, J { }").classes[0]
        self.assertEqual(c.interfaces, ["I", "J"])

    def test_relationship_with_multiplicity_and_name(self):
        r = parse('User "1" --> "*" Product : owns').relationships[0]
        self.assertEqual((r.source, r.target, r.source_multiplicity,
                          r.target_multiplicity, r.name, r.relationship_type),
                         ("User", "Product", "1", "*", "owns", "association"))

    def test_relationship_minimal(self):
        r = parse("A --> B").relationships[0]
        self.assertEqual((r.source_multiplicity, r.target_multiplicity, r.name),
                         (None, None, None))

    def test_multiplicity_forms(self):
        for m in ["1", "*", "0..1", "1..*", "2..5"]:
            r = parse(f'A "{m}" --> B').relationships[0]
            self.assertEqual(r.source_multiplicity, m)

    def test_invalid_multiplicity(self):
        for m in ["abc", "5..2", "*..1", ""]:
            with self.assertRaises(ParserError, msg=m):
                parse(f'A "{m}" --> B')

    def test_multiple_classes_and_comments(self):
        prog = parse("// c\nclass A {}\nclass B {}\nA --> B")
        self.assertEqual([c.name for c in prog.classes], ["A", "B"])
        self.assertEqual(len(prog.relationships), 1)

    def test_missing_closing_brace(self):
        with self.assertRaises(ParserError) as cm:
            parse("class A {\n + x: int\n")
        self.assertIn("'}'", cm.exception.message)

    def test_missing_type(self):
        with self.assertRaises(ParserError) as cm:
            parse("class A { + x: }")
        self.assertEqual((cm.exception.line, cm.exception.column), (1, 16))

    def test_bad_member(self):
        with self.assertRaises(ParserError):
            parse("class A { x }")

    def test_unexpected_top_level(self):
        with self.assertRaises(ParserError):
            parse("{ }")

    def test_abstract_interface_rejected(self):
        with self.assertRaises(ParserError):
            parse("abstract interface I { }")


if __name__ == "__main__":
    unittest.main()
