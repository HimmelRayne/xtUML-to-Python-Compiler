"""CLI entry point: runs the whole pipeline Lexer -> Parser -> Semantic -> Generator."""

import argparse
import os
import pprint
import sys
from dataclasses import asdict

from errors.errors import CompilerError
from generator import PythonGenerator
from lexer import Lexer
from semantic import SemanticAnalyzer
from uml_parser import Parser

DEFAULT_OUTPUT = os.path.join("output", "output.py")


def parse_args(argv):
    ap = argparse.ArgumentParser(
        description="Compile a UML class diagram (.uml) into Python code (.py).")
    ap.add_argument("input", help="path to the .uml source file")
    ap.add_argument("-o", "--output", default=DEFAULT_OUTPUT,
                    help=f"output Python file (default: {DEFAULT_OUTPUT})")
    ap.add_argument("--tokens", action="store_true", help="print the token list")
    ap.add_argument("--ast", action="store_true", help="print the AST")
    return ap.parse_args(argv)


def report(errors, source):
    """Print errors to stderr, each followed by the offending source line."""
    lines = source.splitlines()
    for err in errors:
        print(err, file=sys.stderr)
        if 1 <= err.line <= len(lines):
            text = lines[err.line - 1].replace("\t", " ")
            print(f"  {text}\n  {' ' * (err.column - 1)}^", file=sys.stderr)
        print(file=sys.stderr)
    if len(errors) > 1:
        print(f"{len(errors)} errors found.", file=sys.stderr)


def print_tokens(tokens):
    for t in tokens:
        print(f"  {t.line}:{t.column}".ljust(9) + t.type.name.ljust(12) + repr(t.value))
    print()


def print_ast(program):
    def clean(obj):  # hide position fields to keep the output readable
        if isinstance(obj, dict):
            return {k: clean(v) for k, v in obj.items()
                    if k not in ("line", "column") and not k.endswith("_pos")}
        if isinstance(obj, list):
            return [clean(v) for v in obj]
        return obj
    pprint.pprint(clean(asdict(program)), sort_dicts=False, width=100)
    print()


def main(argv=None):
    args = parse_args(argv)

    try:
        with open(args.input, encoding="utf-8-sig") as f:  # tolerates a BOM
            source = f.read()
    except OSError as e:
        print(f"Error: cannot read '{args.input}': {e.strerror}", file=sys.stderr)
        return 2

    # --- stage 1: lexer + parser -------------------------------------
    print("Parsing...")
    try:
        tokens = Lexer(source).tokenize()
        program = Parser(tokens).parse()
    except CompilerError as e:
        report([e], source)
        return 1
    print("✓ Syntax valid\n")
    if args.tokens:
        print_tokens(tokens)
    if args.ast:
        print_ast(program)

    # --- stage 2: semantic analysis ----------------------------------
    print("Semantic analysis...")
    errors = SemanticAnalyzer().analyze(program)
    if errors:
        report(errors, source)
        return 1
    print("✓ No semantic errors\n")

    # --- stage 3: code generation ------------------------------------
    print("Generating Python...")
    code = PythonGenerator().generate(program)
    out_dir = os.path.dirname(args.output)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    try:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(code)
    except OSError as e:
        print(f"Error: cannot write '{args.output}': {e.strerror}", file=sys.stderr)
        return 2
    print(f"✓ Generated: {args.output}")
    return 0


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):  # avoid UnicodeEncodeError for ✓ on Windows
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
