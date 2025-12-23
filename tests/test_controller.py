import numpy as np
import pytest

from fastcs_secop import SecopError
from fastcs_secop._controllers import format_string_to_prec, secop_dtype_to_numpy_dtype


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
        ("int", np.int32),
        ("double", np.float64),
        ("bool", np.bool_),
    ],
)
def test_secop_dtype_to_numpy_dtype(secop_dtype, np_dtype):
    assert secop_dtype_to_numpy_dtype(secop_dtype) == np_dtype


def test_invalid_secop_dtype_to_numpy_dtype():
    with pytest.raises(
        SecopError, match=r"Cannot handle SECoP dtype 'array' within array/struct/tuple"
    ):
        secop_dtype_to_numpy_dtype("array")
