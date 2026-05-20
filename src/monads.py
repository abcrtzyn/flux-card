from typing import Generic, TypeVar, Callable, Union, Tuple
from error import FluxCardInputTypeError

T = TypeVar("T")
U = TypeVar("U")


class Maybe(Generic[T]):
    def __init__(self, value: T | None) -> None:
        self._value = value

    def map(self, func: Callable[[T], U]) -> "Maybe[U]":
        """Applies a transformation if the value exists, otherwise bypasses."""
        if self._value is None:
            return Maybe[U](None)
        return Maybe[U](func(self._value))

    def validate(self, validator: Callable[[T], None]) -> "Maybe[T]":
        """Runs a validation hook that will throw if invariants are breached."""
        if self._value is not None:
            validator(self._value)
        return self

    def unwrap(self) -> T | None:
        """Returns the inner value or None."""
        return self._value

    def unwrap_or(self, default_factory: Callable[[], T]) -> T:
        """Returns the inner value, or the default if it was None."""
        if self._value is None:
            return default_factory()
        return self._value




class Box(Generic[T]):
    def __init__(self, value: T) -> None:
        self._value = value

    def map(self, func: Callable[[T], U]) -> "Box[U]":
        """Applies a transformation"""
        return Box[U](func(self._value))

    def unwrap(self) -> T:
        """Returns the inner value"""
        return self._value
