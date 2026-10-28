"""Lexer: source text -> list of tokens."""

from dataclasses import dataclass
from enum import Enum, auto

from errors.errors import LexerError


class TokenType(Enum):
    # keywords
    CLASS = auto()
    ABSTRACT = auto()
    INTERFACE = auto()
    EXTENDS = auto()
    IMPLEMENTS = auto()
    # literals
    IDENTIFIER = auto()
    STRING = auto()
    # symbols
    PLUS = auto()
    MINUS = auto()
    HASH = auto()
    COLON = auto()
    LBRACE = auto()
    RBRACE = auto()
    LPAREN = auto()
    RPAREN = auto()
    COMMA = auto()
    ARROW = auto()
    EOF = auto()


KEYWORDS = {
    "class": TokenType.CLASS,
    "abstract": TokenType.ABSTRACT,
    "interface": TokenType.INTERFACE,
    "extends": TokenType.EXTENDS,
    "implements": TokenType.IMPLEMENTS,
}

SINGLE_CHARS = {
    "+": TokenType.PLUS,
    "-": TokenType.MINUS,
    "#": TokenType.HASH,
    ":": TokenType.COLON,
    "{": TokenType.LBRACE,
    "}": TokenType.RBRACE,
    "(": TokenType.LPAREN,
    ")": TokenType.RPAREN,
    ",": TokenType.COMMA,
}


def _is_ident_start(ch):
    return ch != "" and ch.isascii() and (ch.isalpha() or ch == "_")


def _is_ident_char(ch):
    return ch != "" and ch.isascii() and (ch.isalnum() or ch == "_")


@dataclass
class Token:
    type: TokenType
    value: str
    line: int
    column: int


class Lexer:
    def __init__(self, source):
        self.src = source
        self.pos = 0
        self.line = 1
        self.col = 1

    # ---- helpers -------------------------------------------------
    def _peek(self, offset=0):
        i = self.pos + offset
        return self.src[i] if i < len(self.src) else ""

    def _advance(self):
        ch = self.src[self.pos]
        self.pos += 1
        if ch == "\n":
            self.line += 1
            self.col = 1
        else:
            self.col += 1
        return ch

    # ---- main loop -----------------------------------------------
    def tokenize(self):
        tokens = []
        while self.pos < len(self.src):
            ch = self._peek()
            if ch in " \t\r\n":
                self._advance()
            elif ch == "/" and self._peek(1) == "/":
                while self._peek() not in ("", "\n"):
                    self._advance()
            elif ch == "-" and self._peek(1) == "-" and self._peek(2) == ">":
                tokens.append(self._arrow())
            elif ch in SINGLE_CHARS:
                line, col = self.line, self.col
                tokens.append(Token(SINGLE_CHARS[ch], self._advance(), line, col))
            elif ch == '"':
                tokens.append(self._string())
            elif _is_ident_start(ch):
                tokens.append(self._identifier())
            else:
                raise LexerError(f"Unexpected character {ch!r}", self.line, self.col)
        tokens.append(Token(TokenType.EOF, "", self.line, self.col))
        return tokens

    def _arrow(self):
        line, col = self.line, self.col
        for _ in range(3):
            self._advance()
        return Token(TokenType.ARROW, "-->", line, col)

    def _string(self):
        line, col = self.line, self.col
        self._advance()  # opening quote
        chars = []
        while self._peek() != '"':
            if self._peek() in ("", "\n"):
                raise LexerError("Unterminated string", line, col)
            chars.append(self._advance())
        self._advance()  # closing quote
        return Token(TokenType.STRING, "".join(chars), line, col)

    def _identifier(self):
        line, col = self.line, self.col
        chars = []
        while _is_ident_char(self._peek()):
            chars.append(self._advance())
        text = "".join(chars)
        return Token(KEYWORDS.get(text, TokenType.IDENTIFIER), text, line, col)
