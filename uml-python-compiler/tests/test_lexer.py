import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from errors.errors import LexerError
from lexer import Lexer, TokenType as T


def types(src):
    return [t.type for t in Lexer(src).tokenize()]


class TestLexer(unittest.TestCase):
    def test_empty_class(self):
        self.assertEqual(
            types("class A { }"),
            [T.CLASS, T.IDENTIFIER, T.LBRACE, T.RBRACE, T.EOF],
        )

    def test_keywords(self):
        self.assertEqual(
            types("abstract interface extends implements")[:-1],
            [T.ABSTRACT, T.INTERFACE, T.EXTENDS, T.IMPLEMENTS],
        )

    def test_attribute_and_visibility(self):
        self.assertEqual(
            types("+ a: int - b: str # c: bool")[:-1],
            [T.PLUS, T.IDENTIFIER, T.COLON, T.IDENTIFIER,
             T.MINUS, T.IDENTIFIER, T.COLON, T.IDENTIFIER,
             T.HASH, T.IDENTIFIER, T.COLON, T.IDENTIFIER],
        )

    def test_method_symbols(self):
        self.assertEqual(
            types("f(a: int, b: str): bool")[:-1],
            [T.IDENTIFIER, T.LPAREN, T.IDENTIFIER, T.COLON, T.IDENTIFIER, T.COMMA,
             T.IDENTIFIER, T.COLON, T.IDENTIFIER, T.RPAREN, T.COLON, T.IDENTIFIER],
        )

    def test_relationship_and_multiplicity(self):
        toks = Lexer('User "1" --> "0..1" Product : owns').tokenize()
        self.assertEqual(
            [t.type for t in toks][:-1],
            [T.IDENTIFIER, T.STRING, T.ARROW, T.STRING, T.IDENTIFIER, T.COLON, T.IDENTIFIER],
        )
        self.assertEqual(toks[1].value, "1")
        self.assertEqual(toks[3].value, "0..1")

    def test_minus_vs_arrow(self):
        self.assertEqual(types("- x --> y")[:-1], [T.MINUS, T.IDENTIFIER, T.ARROW, T.IDENTIFIER])

    def test_comment_ignored(self):
        self.assertEqual(types("// hello\nclass A {}")[0], T.CLASS)

    def test_line_and_column(self):
        toks = Lexer("class A {\n  + x: int\n}").tokenize()
        plus = next(t for t in toks if t.type == T.PLUS)
        self.assertEqual((plus.line, plus.column), (2, 3))

    def test_unexpected_character(self):
        with self.assertRaises(LexerError) as cm:
            Lexer("class A {\n  @ \n}").tokenize()
        self.assertEqual((cm.exception.line, cm.exception.column), (2, 3))

    def test_unterminated_string(self):
        with self.assertRaises(LexerError):
            Lexer('A "1 --> B').tokenize()


if __name__ == "__main__":
    unittest.main()
