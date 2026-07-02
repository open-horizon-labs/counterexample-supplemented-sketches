from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class ParseError:
    code: str
    message: str


@dataclass(frozen=True)
class Ok(Generic[T]):
    value: T
    ok: bool = True


@dataclass(frozen=True)
class Err:
    error: ParseError
    ok: bool = False


ParseResult = Ok[T] | Err


def ok(value: T) -> Ok[T]:
    return Ok(value=value)


def err(code: str, message: str) -> Err:
    return Err(error=ParseError(code=code, message=message))
