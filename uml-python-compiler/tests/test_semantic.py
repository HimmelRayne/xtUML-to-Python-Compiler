import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lexer import Lexer
from semantic import SemanticAnalyzer
from uml_parser import Parser


def analyze(src):
    analyzer = SemanticAnalyzer()
    errors = analyzer.analyze(Parser(Lexer(src).tokenize()).parse())
    return errors, analyzer.symbols


def messages(src):
    return [e.message for e in analyze(src)[0]]


class TestSemantic(unittest.TestCase):
    def test_valid_model(self):
        src = """
        class User { - id: int + name: str + login(): bool }
        class Admin extends User { + manage(u: User): void }
        class Product { - price: float }
        User "1" --> "*" Product : owns
        """
        self.assertEqual(messages(src), [])

    def test_symbol_table(self):
        _, table = analyze("class A { + x: int + f(): void }")
        sym = table.lookup("A")
        self.assertIn("x", sym.attributes)
        self.assertIn("f", sym.methods)
        self.assertIsNone(table.lookup("B"))

    def test_duplicate_class(self):
        errors, _ = analyze("class A {}\nclass A {}")
        self.assertEqual(len(errors), 1)
        self.assertIn("already defined", errors[0].message)
        self.assertEqual((errors[0].line, errors[0].column), (2, 7))

    def test_unknown_parent(self):
        errors, _ = analyze("class Admin extends User { }")
        self.assertEqual(errors[0].message, "Class 'User' is not defined.")
        self.assertEqual((errors[0].line, errors[0].column), (1, 21))
        self.assertEqual(str(errors[0]),
                         "Semantic Error: Class 'User' is not defined.\nLine 1, Column 21")

    def test_duplicate_attribute(self):
        self.assertIn("Duplicate attribute 'x' in class 'A'.",
                      messages("class A { + x: int - x: str }"))

    def test_duplicate_method(self):
        msgs = messages("class A { + f(): int + f(a: int): int }")
        self.assertTrue(any("Duplicate method 'f'" in m for m in msgs))

    def test_duplicate_parameter(self):
        msgs = messages("class A { + f(a: int, a: str): void }")
        self.assertTrue(any("Duplicate parameter 'a'" in m for m in msgs))

    def test_unknown_attribute_type(self):
        errors, _ = analyze("class A { + x: Foo }")
        self.assertIn("Unknown type 'Foo'", errors[0].message)
        self.assertEqual((errors[0].line, errors[0].column), (1, 16))

    def test_unknown_parameter_and_return_type(self):
        msgs = messages("class A { + f(a: Foo): Bar }")
        self.assertEqual(len(msgs), 2)

    def test_user_class_is_valid_type(self):
        self.assertEqual(messages("class B {} class A { + b: B + f(x: B): B }"), [])

    def test_void_only_as_return_type(self):
        self.assertEqual(messages("class A { + f(): void }"), [])
        self.assertEqual(len(messages("class A { + x: void }")), 1)
        self.assertEqual(len(messages("class A { + f(a: void): int }")), 1)

    def test_class_extends_interface(self):
        msgs = messages("interface I {} class A extends I {}")
        self.assertIn("use 'implements'", msgs[0])

    def test_interface_extends_class(self):
        msgs = messages("class A {} interface I extends A {}")
        self.assertIn("cannot extend class", msgs[0])

    def test_implements_checks(self):
        self.assertEqual(messages("interface I {} class A implements I {}"), [])
        self.assertIn("not an interface", messages("class B {} class A implements B {}")[0])
        self.assertIn("not defined", messages("class A implements Nope {}")[0])
        self.assertIn("cannot use 'implements'",
                      messages("interface I {} interface J implements I {}")[0])

    def test_interface_attributes_rejected(self):
        self.assertIn("cannot declare attributes", messages("interface I { + x: int }")[0])

    def test_circular_inheritance(self):
        msgs = messages("class A extends B {} class B extends A {}")
        self.assertEqual(len(msgs), 1)
        self.assertEqual(msgs[0], "Circular inheritance detected: A -> B -> A")

    def test_self_inheritance(self):
        self.assertEqual(messages("class A extends A {}"),
                         ["Circular inheritance detected: A -> A"])

    def test_relationship_unknown_classes(self):
        errors, _ = analyze("class A {}\nA --> B\nC --> A")
        self.assertEqual([e.message for e in errors],
                         ["Class 'B' is not defined.", "Class 'C' is not defined."])
        self.assertEqual((errors[0].line, errors[0].column), (2, 7))

    def test_multiple_errors_sorted(self):
        errors, _ = analyze("class A extends X { + f(): Y }\nclass B extends Z {}")
        self.assertEqual(len(errors), 3)
        self.assertEqual([e.line for e in errors], sorted(e.line for e in errors))


    def test_reserved_python_words_rejected(self):
        self.assertIn("reserved Python word", messages("class from {}")[0])
        self.assertIn("reserved Python word", messages("class A { + pass: int }")[0])
        self.assertIn("reserved Python word", messages("class A { + f(self: int): void }")[0])
        self.assertIn("reserved Python word", messages("class A {} class B {}\nA --> B : is")[0])

    def test_attribute_method_name_clash(self):
        self.assertIn("both an attribute and a method",
                      messages("class A { + x: int + x(): int }")[0])

    def test_interface_cannot_be_relationship_source(self):
        self.assertIn("cannot be the source",
                      messages("interface I {} class A {}\nI --> A")[0])


if __name__ == "__main__":
    unittest.main()
