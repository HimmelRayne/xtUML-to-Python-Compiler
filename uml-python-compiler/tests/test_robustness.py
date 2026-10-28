"""Regression tests for bugs found by fuzzing + a small deterministic fuzz run."""

import inspect
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from errors.errors import CompilerError, LexerError
from generator import PythonGenerator
from lexer import Lexer
from semantic import SemanticAnalyzer
from uml_parser import Parser


def front(src):
    program = Parser(Lexer(src).tokenize()).parse()
    return program, SemanticAnalyzer().analyze(program)


def compile_ok(src):
    program, errors = front(src)
    assert not errors, [str(e) for e in errors]
    code = PythonGenerator().generate(program)
    compile(code, "<generated>", "exec")
    return code


class TestRegressions(unittest.TestCase):
    def test_derived_field_name_is_not_a_keyword(self):
        # target "As" -> default field name "as" (a Python keyword)
        code = compile_ok('class A {} class As {}\nA --> As')
        self.assertIn("self.as_: As | None = None", code)

    def test_non_ascii_identifier_rejected(self):
        with self.assertRaises(LexerError):
            Lexer("class A² {}").tokenize()

    def test_class_named_like_builtin_or_generated_import(self):
        for name in ("int", "string", "void", "ABC", "abstractmethod"):
            _, errors = front(f"class {name} {{}}")
            self.assertTrue(any("reserved" in e.message for e in errors), name)


class TestFuzz(unittest.TestCase):
    NAMES = ["A", "B", "C", "D", "E"]

    def random_model(self, rng):
        names = self.NAMES[: rng.randint(1, 5)]
        parts = []
        for n in names:
            kind = rng.choice(["class", "class", "abstract class", "interface"])
            head = f"{kind} {n}"
            if rng.random() < 0.5:
                head += f" extends {rng.choice(names)}"
            if kind != "interface" and rng.random() < 0.3:
                head += " implements " + ", ".join(rng.sample(names, rng.randint(1, min(2, len(names)))))
            body = []
            if kind != "interface":
                for _ in range(rng.randint(0, 3)):
                    body.append(f"{rng.choice(['+', '-', '#', ''])} {rng.choice(['x', 'y', 'id'])}: "
                                f"{rng.choice(['int', 'str', 'bool'] + names)}")
            for _ in range(rng.randint(0, 3)):
                ps = ", ".join(f"{p}: {rng.choice(['int', 'str'] + names)}"
                               for p in rng.sample(["a", "b", "c"], rng.randint(0, 2)))
                body.append(f"{rng.choice(['+', '-', '#', ''])} {rng.choice(['f', 'g'])}({ps})"
                            + rng.choice(["", ": void", ": int"]))
            parts.append(head + " {\n  " + "\n  ".join(body) + "\n}")
        for _ in range(rng.randint(0, 3)):
            mult = lambda: rng.choice(["", '"1" ', '"*" ', '"0..1" ', '"1..*" '])
            parts.append(f"{rng.choice(names)} {mult()}--> {mult()}{rng.choice(names)}"
                         + rng.choice(["", " : link"]))
        rng.shuffle(parts)
        return "\n".join(parts)

    def test_valid_random_models_generate_working_python(self):
        rng = random.Random(7)
        valid = 0
        for _ in range(2000):
            src = self.random_model(rng)
            program, errors = front(src)
            if errors:
                continue
            valid += 1
            ns = {}
            exec(compile(PythonGenerator().generate(program), "<g>", "exec"), ns)
            for name in self.NAMES:
                cls = ns.get(name)
                if cls is None or getattr(cls, "__abstractmethods__", None):
                    continue
                n = len(inspect.signature(cls.__init__).parameters) - 1 \
                    if cls.__init__ is not object.__init__ else 0
                cls(*([0] * n))  # constructor chain must work
        self.assertGreater(valid, 50)  # make sure the fuzzer really reaches the generator

    def test_garbage_only_raises_compiler_errors(self):
        rng = random.Random(3)
        alphabet = list('class abstract interface extends implements {}()+-#:,"*.>/\nAB x1 0..')
        for _ in range(3000):
            s = "".join(rng.choice(alphabet) for _ in range(rng.randint(0, 40)))
            try:
                Parser(Lexer(s).tokenize()).parse()
            except CompilerError:
                pass  # any other exception type would fail the test


if __name__ == "__main__":
    unittest.main()
