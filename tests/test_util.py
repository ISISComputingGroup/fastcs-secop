import numpy as np
import pytest
from fastcs.datatypes import Bool, Enum, Float, Int, String, Table, Waveform

from fastcs_secop._util import (
    SecopError,
    format_string_to_prec,
    secop_datainfo_to_fastcs_dtype,
    secop_dtype_to_numpy_dtype,
)


@pytest.mark.parametrize(
    ("secop_fmt", "prec"),
    [
        ("%.1f", 1),
        ("%.99f", 99),
        ("%.5g", None),
        ("%.5e", None),
        (None, None),
    ],
)
def test_format_string_to_prec(secop_fmt, prec):
    assert format_string_to_prec(secop_fmt) == prec


@pytest.mark.parametrize(
    ("secop_dtype", "np_dtype"),
    [
        ({"type": "int"}, np.int32),
        ({"type": "double"}, np.float64),
        ({"type": "bool"}, np.uint8),
        ({"type": "enum"}, np.int32),
        ({"type": "string", "maxchars": 123}, "<U123"),
        ({"type": "string"}, "<U65536"),
    ],
)
def test_secop_dtype_to_numpy_dtype(secop_dtype, np_dtype):
    assert secop_dtype_to_numpy_dtype(secop_dtype) == np_dtype


def test_invalid_secop_dtype_to_numpy_dtype():
    with pytest.raises(
        SecopError, match=r"Cannot handle SECoP dtype 'array' within array/struct/tuple"
    ):
        secop_dtype_to_numpy_dtype({"type": "array"})


@pytest.mark.parametrize(
    ("datainfo", "expected_dtype"),
    [
        ({"type": "double"}, Float),
        ({"type": "scaled"}, Float),
        ({"type": "int"}, Int),
        ({"type": "bool"}, Bool),
        ({"type": "enum", "members": {"nope": 0, "yep": 1}}, Enum),
        ({"type": "string"}, String),
        ({"type": "blob", "maxbytes": 8}, Waveform),
        ({"type": "array", "maxlen": 8, "members": {"type": "int"}}, Waveform),
        ({"type": "tuple", "members": [{"type": "int"}]}, Table),
        ({"type": "struct", "members": {"int": {"type": "int"}}}, Table),
        (
            {"type": "matrix", "elementtype": "<f4", "names": ["x", "y"], "maxlen": [100, 100]},
            Waveform,
        ),
    ],
)
def test_secop_datainfo_to_fastcs_dtype(datainfo, expected_dtype):
    assert isinstance(secop_datainfo_to_fastcs_dtype(datainfo), expected_dtype)


def test_invalid_secop_datainfo_to_fastcs_dtype():
    with pytest.raises(SecopError):
        secop_datainfo_to_fastcs_dtype({"type": "some_type_that_does_not_exist"})


def test_secop_datainfo_to_fastcs_dtype_raw():
    assert isinstance(
        secop_datainfo_to_fastcs_dtype({"type": "some_type_that_does_not_exist"}, raw=True), String
    )
