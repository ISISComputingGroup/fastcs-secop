import enum
import typing
from collections.abc import Collection
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import numpy.typing as npt
from fastcs.datatypes import Bool, DataType, Enum, Float, Int, String, Table, Waveform


@dataclass(frozen=True)
class SecopQuirks:
    """Define special handling for SECoP modules or accessibles.

    Not all combinations of SECoP features can be handled by all
    transports. :py:obj:`SecopQuirks` allows specifying non-default
    behaviour to work around these limitations.
    """

    update_period: float = 1.0
    """Update period, in seconds."""

    skip_modules: Collection[str] = field(default_factory=list)
    """Skip creating any listed modules."""

    skip_accessibles: Collection[tuple[str, str]] = field(default_factory=list)
    """Skip creating any listed ``(module_name, accessible_name)`` tuples."""

    raw_accessibles: Collection[tuple[str, str]] = field(default_factory=list)
    """Create any listed ``(module_name, accessible_name)`` tuples in raw mode.

    JSON for the specified accessibles will be treated as strings.
    """

    raw_array: bool = False
    """If the accessible has an array type, read it in raw mode.

    JSON values for any array-type accessible will be treated as strings.
    """

    raw_matrix: bool = False
    """If the accessible has a matrix type, read it in raw mode.

    JSON values for any matrix-type accessible will be treated as strings.

    This is useful for transports which cannot represent arbitrary N-dimensional
    arrays.
    """

    raw_tuple: bool = False
    """If the accessible has a tuple type, read it in raw mode.

    JSON values for any tuple-type accessible will be treated as strings.

    This is useful for transports which do not support the FastCS
    :py:obj:`~fastcs.datatypes.table.Table` type.
    """

    raw_struct: bool = False
    """If the accessible has a struct type, read it in raw mode.

    JSON values for any struct-type accessible will be treated as strings.

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
        return np.uint8  # CA transport doesn't support bool_
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


def secop_datainfo_to_fastcs_dtype(datainfo: dict[str, Any], raw: bool = False) -> DataType[Any]:
    """Convert a SECoP datainfo dictionary to a FastCS data type.

    Args:
        datainfo: SECoP datainfo dictionary.
        raw: whether to read this parameter in 'raw' mode.

    """
    if raw:
        return String(2048)

    min_val = datainfo.get("min")
    max_val = datainfo.get("max")

    match datainfo["type"]:
        case "double" | "scaled":
            scale = datainfo.get("scale")

            if min_val is not None and scale is not None:
                min_val *= scale
            if max_val is not None and scale is not None:
                max_val *= scale

            return Float(
                units=datainfo.get("unit", None),
                min_alarm=min_val,
                max_alarm=max_val,
                prec=format_string_to_prec(datainfo.get("fmtstr", None)),  # type: ignore
            )
        case "int":
            return Int(
                units=datainfo.get("unit", None),
                min_alarm=min_val,
                max_alarm=max_val,
            )
        case "bool":
            return Bool()
        case "enum":
            enum_type = enum.Enum("GeneratedSecopEnum", datainfo["members"])
            return Enum(enum_type)
        case "string":
            return String()
        case "blob":
            return Waveform(np.uint8, shape=(datainfo["maxbytes"],))
        case "array":
            inner_dtype = datainfo["members"]
            np_inner_dtype = secop_dtype_to_numpy_dtype(inner_dtype)
            return Waveform(np_inner_dtype, shape=(datainfo["maxlen"],))
        case "tuple":
            structured_dtype = tuple_structured_dtype(datainfo)
            return Table(structured_dtype)
        case "struct":
            structured_dtype = struct_structured_dtype(datainfo)
            return Table(structured_dtype)
        case "matrix":
            return Waveform(datainfo["elementtype"], shape=datainfo["maxlen"][::-1])
        case _:
            raise SecopError(f"Invalid SECoP dtype for FastCS attribute: {datainfo['type']}")


def is_raw(
    module_name: str, parameter_name: str, datainfo: dict[str, typing.Any], quirks: SecopQuirks
) -> bool:
    return (
        ((module_name, parameter_name) in quirks.raw_accessibles)
        or (datainfo["type"] == "array" and quirks.raw_array)
        or (datainfo["type"] == "tuple" and quirks.raw_tuple)
        or (datainfo["type"] == "struct" and quirks.raw_struct)
        or (datainfo["type"] == "matrix" and quirks.raw_matrix)
    )
