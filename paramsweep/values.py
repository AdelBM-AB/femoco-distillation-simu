"""How a parameter value is stored: as JSON in a manifest, and as text in a result path.

The bottom layer, shared by ``parameters`` (which declares values) and ``naming`` (which writes them
into paths and reads them back). Every value that reaches a path goes through ``to_path_str``, and
every comparison against a path goes through it too, so a value and its path spelling cannot drift
apart.

A parameter's ``parse`` must invert ``to_path_str``: whatever a path holds has to read back as the
value that was written. ``parse_bool`` and ``optional`` cover the two cases a plain type does not --
``bool("False")`` is ``True``, and ``int("None")`` raises. ``ParameterSlot`` checks every default
against its parser at import, and ``ExperimentTypeManifest.path_for`` checks every value it writes.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional, TypeVar

import numpy as np

T = TypeVar("T")

_TRUE = frozenset({"true", "1", "yes"})
_FALSE = frozenset({"false", "0", "no"})
_NONE = frozenset({"none", "null"})


def jsonable(value: Any) -> Any:
    """Coerce a parameter value into something ``json.dumps`` accepts."""
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, np.generic):
        return value.item()
    return value


def to_path_str(value: Any) -> str:
    """The text a value takes in a result path. An enum is spelled by its ``value``, whatever its
    ``__str__`` says."""
    return str(jsonable(value))


def parse_bool(value: Any) -> bool:
    """A bool from a bool, or from the text a path holds (``"True"``, ``"false"``, ``"1"``...).

    Strict: anything else raises, rather than reading as ``False``.
    """
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, (int, np.integer)) and value in (0, 1):
        return bool(value)
    text = str(value).strip().lower()
    if text in _TRUE:
        return True
    if text in _FALSE:
        return False
    raise ValueError(f"not a boolean: {value!r}")


def optional(parse: Callable[[Any], T]) -> Callable[[Any], Optional[T]]:
    """``parse``, but reading ``None`` -- and its path spellings ``"None"``/``"null"`` -- as
    ``None``."""

    def parse_optional(value: Any) -> Optional[T]:
        if value is None or (isinstance(value, str) and value.strip().lower() in _NONE):
            return None
        return parse(value)

    parse_optional.__qualname__ = f"optional({getattr(parse, '__qualname__', parse)!s})"
    return parse_optional
