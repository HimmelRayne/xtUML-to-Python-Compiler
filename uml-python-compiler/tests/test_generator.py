import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from generator import PythonGenerator
from lexer import Lexer
from semantic import SemanticAnalyzer
from uml_parser import Parser


def generate(src):
    program = Parser(Lexer(src).tokenize()).parse()
    errors = SemanticAnalyzer().analyze(program)
    assert not errors, [str(e) for e in errors]
    code = PythonGenerator().generate(program)
    compile(code, "<generated>", "exec")  # must be valid Python
    return code


def run(src):
    """Generate, compile and execute; return the resulting namespace."""
    ns = {}
    exec(compile(generate(src), "<generated>", "exec"), ns)
    return ns


class TestGenerator(unittest.TestCase):
    def test_empty_class(self):
        self.assertIn("class A:\n    pass", generate("class A { }"))

    def test_attributes_and_methods_match_spec_example(self):
        code = generate("class User { - id: int + name: str + login(): bool }")
        self.assertIn("class User:", code)
        self.assertIn("def __init__(self, id: int, name: str):", code)
        self.assertIn("self._id = id", code)
        self.assertIn("self.name = name", code)
        self.assertIn("def login(self) -> bool:", code)

    def test_protected_and_private_use_underscore(self):
        ns = run("class A { # e: str - p: int + f(): void - g(): void }")
        obj = ns["A"]("x", 1)
        self.assertEqual((obj._e, obj._p), ("x", 1))
        self.assertTrue(hasattr(obj, "_g") and hasattr(obj, "f"))

    def test_type_mapping_and_params(self):
        code = generate("class A { + f(a: string, b: float, c: bool): void }")
        self.assertIn("def f(self, a: str, b: float, c: bool) -> None:", code)

    def test_default_return_type_is_none(self):
        self.assertIn("def run(self) -> None:", generate("class A { + run() }"))

    def test_inheritance(self):
        code = generate("class Admin extends User { + manageUser(): void }\n"
                        "class User { + name: str }")
        self.assertIn("class Admin(User):", code)
        self.assertLess(code.index("class User"), code.index("class Admin"))  # reordered
        self.assertIn("def manageUser(self) -> None:", code)

    def test_subclass_constructor_chain(self):
        ns = run("class User { - id: int + name: str }\n"
                 "class Admin extends User { + level: int }")
        admin = ns["Admin"](1, "root", 9)
        self.assertEqual((admin._id, admin.name, admin.level), (1, "root", 9))

    def test_subclass_without_new_attributes_inherits_init(self):
        ns = run("class A { + x: int } class B extends A { + f(): void } "
                 "class C extends B { + y: int }")
        c = ns["C"](1, 2)
        self.assertEqual((c.x, c.y), (1, 2))
        self.assertEqual(ns["B"](5).x, 5)

    def test_abstract_class(self):
        ns = run("abstract class Animal { + makeSound(): void }\n"
                 "class Dog extends Animal { + makeSound(): void }")
        with self.assertRaises(TypeError):
            ns["Animal"]()
        ns["Dog"]()  # concrete subclass overrides the method

    def test_interface_and_implements(self):
        code = generate("interface I { + f(): int } interface J extends I { + g(): int }\n"
                        "class C implements I, J { + f(): int + g(): int }")
        self.assertIn("from abc import ABC, abstractmethod", code)
        self.assertIn("class I(ABC):", code)
        self.assertIn("class J(I):", code)
        run("interface I { + f(): int } interface J extends I { + g(): int }\n"
            "class C implements I, J { + f(): int + g(): int }")["C"]()

    def test_many_association_uses_list(self):
        ns = run('class User { + n: str } class Product { + p: str }\n'
                 'User "1" --> "*" Product : owns')
        self.assertEqual(ns["User"]("a").owns, [])

    def test_single_association_uses_optional(self):
        code = generate('class A {} class B {}\nA --> "0..1" B')
        self.assertIn("self.b: B | None = None", code)

    def test_default_association_name_and_multiplicity_range(self):
        code = generate('class A {} class B {}\nA "1" --> "1..*" B')
        self.assertIn("self.bs: list[B] = []", code)
        self.assertIn('# association: A "1" --> "1..*" B', code)

    def test_association_forward_reference_and_with_attributes(self):
        ns = run('class A { + x: int }\nclass B extends A {}\nA --> "*" C\nclass C {}')
        self.assertEqual(ns["A"](1).cs, [])

    def test_relationship_name_clash_is_avoided(self):
        code = generate('class A {} class B {} class C {}\nA --> B : link\nA --> C : link')
        self.assertIn("self.link: B", code)
        self.assertIn("self.link_: C", code)

    def test_multiple_classes(self):
        ns = run("class A {} class B {} class C extends B {}")
        self.assertTrue(all(n in ns for n in "ABC"))

    def test_generated_header(self):
        code = generate("class A {}")
        self.assertTrue(code.startswith("# Generated by"))
        self.assertIn("from __future__ import annotations", code)
        self.assertNotIn("abc", code.split("class")[0].replace("# Generated", ""))


if __name__ == "__main__":
    unittest.main()
