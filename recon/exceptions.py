"""Domain exceptions raised by parsers, loaders and services."""


class ParseError(Exception):
    """Raised when a statement or ledger file cannot be parsed."""


class ReviewError(Exception):
    """Raised when a match cannot be reviewed."""
