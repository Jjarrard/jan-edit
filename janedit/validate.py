"""Cheap structural validation of a proposed edit, before it touches disk.

A small model's single most common damaging failure is an edit that is
*plausible* but syntactically broken - a dedented line, a dropped bracket, a
half-replaced block. Catching that here turns a silent corruption into a
specific, actionable error the model can retry against, and costs nothing
compared to another model round-trip.

Validation is best-effort by design: an unknown file type is not an error,
and a validator that can't run never blocks an edit.
"""

from __future__ import annotations

import ast
import configparser
import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ValidationResult:
    ok: bool
    message: str = ""

    @classmethod
    def good(cls) -> "ValidationResult":
        return cls(True)

    @classmethod
    def bad(cls, message: str) -> "ValidationResult":
        return cls(False, message)


def _validate_python(text: str) -> ValidationResult:
    try:
        ast.parse(text)
    except SyntaxError as exc:
        where = f"line {exc.lineno}" if exc.lineno else "unknown line"
        return ValidationResult.bad(f"Python syntax error at {where}: {exc.msg}")
    except ValueError as exc:  # e.g. null bytes
        return ValidationResult.bad(f"Python parse error: {exc}")
    return ValidationResult.good()


def _validate_json(text: str) -> ValidationResult:
    if not text.strip():
        return ValidationResult.good()
    try:
        json.loads(text)
    except json.JSONDecodeError as exc:
        return ValidationResult.bad(f"JSON error at line {exc.lineno}, column {exc.colno}: {exc.msg}")
    return ValidationResult.good()


def _validate_ini(text: str) -> ValidationResult:
    try:
        configparser.ConfigParser().read_string(text)
    except configparser.Error as exc:
        return ValidationResult.bad(f"INI/config error: {exc}")
    return ValidationResult.good()


def _balanced_delimiters(text: str) -> ValidationResult:
    """Bracket balance check for languages we have no real parser for.

    Deliberately conservative: it ignores anything inside strings or comments
    and only reports a definite mismatch, because a false positive here would
    block a perfectly good edit.
    """
    pairs = {")": "(", "]": "[", "}": "{"}
    openers = set(pairs.values())
    stack: list[str] = []

    i = 0
    n = len(text)
    line = 1
    in_line_comment = False
    in_block_comment = False
    quote: str | None = None

    while i < n:
        ch = text[i]
        nxt = text[i + 1] if i + 1 < n else ""

        if ch == "\n":
            line += 1
            in_line_comment = False
            i += 1
            continue

        if in_line_comment:
            i += 1
            continue
        if in_block_comment:
            if ch == "*" and nxt == "/":
                in_block_comment = False
                i += 2
                continue
            i += 1
            continue
        if quote:
            if ch == "\\":
                i += 2
                continue
            if ch == quote:
                quote = None
            i += 1
            continue

        if ch == "/" and nxt == "/":
            in_line_comment = True
            i += 2
            continue
        if ch == "/" and nxt == "*":
            in_block_comment = True
            i += 2
            continue
        if ch in ("'", '"', "`"):
            quote = ch
            i += 1
            continue

        if ch in openers:
            stack.append(ch)
        elif ch in pairs:
            if not stack:
                return ValidationResult.bad(f"unbalanced '{ch}' at line {line} (nothing open to close)")
            if stack[-1] != pairs[ch]:
                return ValidationResult.bad(f"mismatched '{ch}' at line {line}")
            stack.pop()
        i += 1

    if stack:
        return ValidationResult.bad(f"{len(stack)} unclosed '{stack[-1]}' by end of file")
    return ValidationResult.good()


BRACKET_LANGUAGES = {".js", ".jsx", ".ts", ".tsx", ".c", ".h", ".cpp", ".hpp", ".java", ".go", ".rs", ".css"}


def validate(rel_path: str, text: str) -> ValidationResult:
    """Validate proposed file content by extension. Unknown types always pass."""
    suffix = Path(rel_path).suffix.lower()
    if suffix == ".py":
        return _validate_python(text)
    if suffix == ".json":
        return _validate_json(text)
    if suffix in (".ini", ".cfg", ".toml"):
        # TOML is close enough to INI for a smoke test; a real TOML parser
        # would reject valid INI and vice versa, so only flag hard failures.
        return ValidationResult.good() if suffix == ".toml" else _validate_ini(text)
    if suffix in BRACKET_LANGUAGES:
        return _balanced_delimiters(text)
    return ValidationResult.good()
