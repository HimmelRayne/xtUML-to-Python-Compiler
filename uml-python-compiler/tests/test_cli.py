"""End-to-end tests: run the CLI on real files and check the generated Python."""

import contextlib
import glob
import io
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import main as cli

VALID = sorted(glob.glob(os.path.join(ROOT, "examples", "*.uml")))
INVALID = sorted(glob.glob(os.path.join(ROOT, "examples", "invalid", "*.uml")))

SPEC_EXAMPLE = '''
class User {
    - id: int
    + name: str
    # email: str

    + login(): bool
    + changePassword(password: str): void
}

class Admin extends User {
    + manageUser(user: User): void
}

class Product {
    - id: int
    - name: str
    - price: float
}

User "1" --> "*" Product : owns
'''


def run_cli(args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli.main(args)
    return code, out.getvalue(), err.getvalue()


class TestCLI(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def path(self, name):
        return os.path.join(self.tmp.name, name)

    def write(self, name, text, **kw):
        p = self.path(name)
        with open(p, "w", encoding=kw.pop("encoding", "utf-8"), newline="") as f:
            f.write(text)
        return p

    def compile_file(self, src_path):
        out_path = self.path("out/result.py")
        code, out, err = run_cli([src_path, "-o", out_path])
        return code, out, err, out_path

    # ---- valid inputs ---------------------------------------------
    def test_examples_exist(self):
        self.assertGreaterEqual(len(VALID), 3)
        self.assertGreaterEqual(len(INVALID), 2)

    def test_all_valid_examples_compile_and_run(self):
        for src in VALID:
            with self.subTest(example=os.path.basename(src)):
                code, out, err, out_path = self.compile_file(src)
                self.assertEqual(code, 0, err)
                self.assertIn("✓ Syntax valid", out)
                self.assertIn("✓ No semantic errors", out)
                self.assertIn(f"✓ Generated: {out_path}", out)
                with open(out_path, encoding="utf-8") as f:
                    py = f.read()
                exec(compile(py, out_path, "exec"), {})  # valid and importable

    def test_spec_example_end_to_end(self):
        code, _, err, out_path = self.compile_file(self.write("spec.uml", SPEC_EXAMPLE))
        self.assertEqual(code, 0, err)
        ns = {}
        with open(out_path, encoding="utf-8") as f:
            exec(f.read(), ns)
        admin = ns["Admin"](1, "root", "r@x.id")
        self.assertEqual(admin.name, "root")
        self.assertEqual(ns["User"](2, "u", "e").owns, [])

    def test_output_directory_is_created(self):
        code, _, _, out_path = self.compile_file(self.write("a.uml", "class A {}"))
        self.assertEqual(code, 0)
        self.assertTrue(os.path.isfile(out_path))

    def test_tokens_and_ast_flags(self):
        src = self.write("a.uml", "class A { + x: int }")
        code, out, _ = run_cli([src, "-o", self.path("o.py"), "--tokens", "--ast"])
        self.assertEqual(code, 0)
        self.assertIn("IDENTIFIER", out)
        self.assertIn("'attributes'", out)

    # ---- edge cases -----------------------------------------------
    def test_empty_file(self):
        code, _, err, out_path = self.compile_file(self.write("e.uml", ""))
        self.assertEqual(code, 0, err)
        with open(out_path, encoding="utf-8") as f:
            compile(f.read(), out_path, "exec")

    def test_windows_line_endings(self):
        src = self.write("w.uml", "class A {\r\n  + x: int\r\n}\r\n")
        self.assertEqual(self.compile_file(src)[0], 0)

    def test_utf8_bom(self):
        src = self.write("b.uml", "class A {}", encoding="utf-8-sig")
        self.assertEqual(self.compile_file(src)[0], 0)

    # ---- invalid inputs -------------------------------------------
    def test_syntax_error_example(self):
        src = os.path.join(ROOT, "examples", "invalid", "syntax_error.uml")
        code, out, err, out_path = self.compile_file(src)
        self.assertEqual(code, 1)
        self.assertIn("Syntax Error", err)
        self.assertIn("Line 3, Column 12", err)
        self.assertNotIn("Semantic analysis", out)   # pipeline stops early
        self.assertFalse(os.path.exists(out_path))   # nothing generated

    def test_semantic_error_example(self):
        src = os.path.join(ROOT, "examples", "invalid", "semantic_error.uml")
        code, out, err, out_path = self.compile_file(src)
        self.assertEqual(code, 1)
        self.assertIn("✓ Syntax valid", out)
        self.assertEqual(err.count("Semantic Error"), 4)
        self.assertIn("4 errors found.", err)
        self.assertNotIn("Generating", out)
        self.assertFalse(os.path.exists(out_path))

    def test_all_invalid_examples_fail(self):
        for src in INVALID:
            with self.subTest(example=os.path.basename(src)):
                self.assertEqual(self.compile_file(src)[0], 1)

    def test_lexer_error_reported_as_syntax_error(self):
        code, _, err, _ = self.compile_file(self.write("l.uml", "class A {\n  @\n}"))
        self.assertEqual(code, 1)
        self.assertIn("Syntax Error: Unexpected character '@'", err)
        self.assertIn("Line 2, Column 3", err)

    def test_missing_input_file(self):
        code, _, err, _ = self.compile_file(self.path("nope.uml"))
        self.assertEqual(code, 2)
        self.assertIn("cannot read", err)


if __name__ == "__main__":
    unittest.main()
