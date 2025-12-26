from unittest.mock import AsyncMock, patch

import numpy as np
import pytest
from fastcs.connections import IPConnectionSettings

from fastcs_secop import SecopError
from fastcs_secop.controllers import (
    SecopController,
    format_string_to_prec,
    secop_dtype_to_numpy_dtype,
)


@pytest.fixture
def controller():
    controller = SecopController(
        settings=IPConnectionSettings(
            ip="127.0.0.1",
            port=65535,
        )
    )
    return controller


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


async def test_ping_happy_path(controller):
    with patch.object(controller._connection, "send_query", AsyncMock(return_value="pong")):
        controller.connect = AsyncMock()
        await controller.ping()
        controller.connect.assert_not_awaited()


async def test_ping_raises_disconnected_error(controller):
    with patch.object(controller._connection, "send_query", AsyncMock(side_effect=ConnectionError)):
        controller.connect = AsyncMock()
        await controller.ping()
        controller.connect.assert_awaited()


async def test_ping_raises_disconnected_error_and_reconnect_fails(controller):
    with patch.object(controller._connection, "send_query", AsyncMock(side_effect=ConnectionError)):
        controller.connect = AsyncMock(side_effect=ConnectionError)
        await controller.ping()
        controller.connect.assert_awaited()
