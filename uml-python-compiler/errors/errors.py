"""Exception classes shared by all compiler stages."""


class CompilerError(Exception):
    """Base error. Every error carries a source location."""

    label = "Error"

    def __init__(self, message, line, column):
        super().__init__(message)
        self.message = message
        self.line = line
        self.column = column

    def __str__(self):
        return f"{self.label}: {self.message}\nLine {self.line}, Column {self.column}"


class LexerError(CompilerError):
    label = "Syntax Error"


class ParserError(CompilerError):
    label = "Syntax Error"


class SemanticError(CompilerError):
    label = "Semantic Error"
