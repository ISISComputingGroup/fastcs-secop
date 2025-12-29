from collections.abc import Collection
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import numpy.typing as npt


@dataclass(frozen=True)
class SecopQuirks:
    """Define special handling for SECoP modules or accessibles.

    Not all combinations of SECoP features can be handled by all
    transports. :py:obj:`SecopQuirks` allows specifying non-default
    behaviour to work around these limitations.
    """

    update_period: float = 1.0
    """Update period, in seconds, for this accessible."""

    skip_modules: Collection[str] = field(default_factory=list)
    """Skip creating any listed modules."""

    skip_accessibles: Collection[tuple[str, str]] = field(default_factory=list)
    """Skip creating any listed (module_name, accessible_name) tuples."""

    raw_accessibles: Collection[tuple[str, str]] = field(default_factory=list)
    """Create any listed (module_name, accessible_name) tuples in 'raw' mode."""

    raw_array: bool = False
    """If the accessible has an array type, read it in raw mode.

    This is useful for accessibles which contain unsupportable arrays
    (e.g. nested, potentially ragged, arrays).
    """
    raw_tuple: bool = False
    """If the accessible has a tuple type, read it in raw mode.

    This is useful for transports which do not support the FastCS
    :py:obj:`~fastcs.datatypes.table.Table` type.
    """
    raw_struct: bool = False
    """If the accessible has a struct type, read it in raw mode.

    This is useful for transports which do not support the FastCS
    :py:obj:`~fastcs.datatypes.table.Table` type.
    """
    max_description_length: int | None = None
    """Truncate accessible descriptions to this length.

    This is useful for transports such as EPICS CA which have a maximum description length.
    """


class SecopError(Exception):
    """Error raised to identify a SECoP protocol or configuration problem."""


def format_string_to_prec(fmt_str: str | None) -> int | None:
    """Convert a SECoP format-string specifier to a precision."""
    if fmt_str is None:
        return None

    if fmt_str.startswith("%.") and fmt_str.endswith("f"):
        return int(fmt_str[2:-1])

    return None


def secop_dtype_to_numpy_dtype(secop_datainfo: dict[str, Any]) -> npt.DTypeLike:
    dtype = secop_datainfo["type"]
    if dtype == "double":
        return np.float64
    elif dtype == "int":
        return np.int32
    elif dtype == "bool":
        return np.uint8
    elif dtype == "enum":
        return np.int32
    elif dtype == "string":
        return f"<U{secop_datainfo.get('maxchars', 65536)}"
    else:
        raise SecopError(
            f"Cannot handle SECoP dtype '{secop_datainfo['type']}' within array/struct/tuple"
        )


def tuple_structured_dtype(datainfo: dict[str, Any]) -> list[tuple[str, npt.DTypeLike]]:
    secop_dtypes = [t for t in datainfo["members"]]
    np_dtypes = [secop_dtype_to_numpy_dtype(t) for t in secop_dtypes]
    names = [f"e{n}" for n in range(len(datainfo["members"]))]
    structured_np_dtype = list(zip(names, np_dtypes, strict=True))
    return structured_np_dtype


def struct_structured_dtype(datainfo: dict[str, Any]) -> list[tuple[str, npt.DTypeLike]]:
    structured_np_dtype = [
        (k, secop_dtype_to_numpy_dtype(v)) for k, v in datainfo["members"].items()
    ]
    return structured_np_dtype
