import enum
from unittest.mock import AsyncMock, patch

import numpy as np
import pytest
from fastcs.attributes import AttrRW
from fastcs.connections import IPConnection

from fastcs_secop import SecopError
from fastcs_secop._io import (
    SecopAttributeIO,
    SecopRawAttributeIO,
    decode,
    encode,
    secop_change,
    secop_read,
)
from fastcs_secop._util import secop_datainfo_to_fastcs_dtype


async def test_read_accessible_success():
    mock_connection = AsyncMock()
    mock_connection.send_query.return_value = "reply some_module:some_accessible {'blah': 'blah'}\n"

    await secop_read(
        connection=mock_connection, module_name="some_module", accessible_name="some_accessible"
    )

    mock_connection.send_query.assert_awaited_once_with("read some_module:some_accessible\n")


async def test_read_accessible_failure():
    mock_connection = AsyncMock()
    mock_connection.send_query.return_value = (
        "error_read some_module:some_accessible {'blah': 'blah'}\n"
    )

    with pytest.raises(SecopError):
        await secop_read(
            connection=mock_connection, module_name="some_module", accessible_name="some_accessible"
        )

    mock_connection.send_query.assert_awaited_once_with("read some_module:some_accessible\n")


async def test_change_accessible_success():
    mock_connection = AsyncMock()
    mock_connection.send_query.return_value = (
        "changed some_module:some_accessible {'blah': 'blah'}\n"
    )

    await secop_change(
        connection=mock_connection,
        module_name="some_module",
        accessible_name="some_accessible",
        encoded_value="{'blah': 'blah'}",
    )

    mock_connection.send_query.assert_awaited_once_with(
        "change some_module:some_accessible {'blah': 'blah'}\n"
    )


async def test_change_accessible_failure():
    mock_connection = AsyncMock()
    mock_connection.send_query.return_value = (
        "error_change some_module:some_accessible {'blah': 'blah'}\n"
    )

    with pytest.raises(SecopError):
        await secop_change(
            connection=mock_connection,
            module_name="some_module",
            accessible_name="some_accessible",
            encoded_value="{'blah': 'blah'}",
        )

    mock_connection.send_query.assert_awaited_once_with(
        "change some_module:some_accessible {'blah': 'blah'}\n"
    )


class DummyEnum(enum.Enum):
    ONE = 1
    TWO = 2
    THREE = 3


@pytest.mark.parametrize(
    ("decoded", "datainfo", "encoded"),
    [
        (1.23, {"type": "double"}, "1.23"),
        (125.5, {"type": "scaled", "scale": 0.1}, "1255"),
        (42, {"type": "int"}, "42"),
        (True, {"type": "bool"}, "true"),
        (DummyEnum.TWO, {"type": "enum", "members": {"ONE": 1, "TWO": 2, "THREE": 3}}, "2"),
        ("hello", {"type": "string"}, '"hello"'),
        (np.frombuffer(b"\0", dtype=np.uint8), {"type": "blob", "maxbytes": 512}, '"AA=="'),
        (np.frombuffer(b"SECoP", dtype=np.uint8), {"type": "blob", "maxbytes": 512}, '"U0VDb1A="'),
        (
            np.array([3, 4, 7, 2, 1], dtype=np.int32),
            {"type": "array", "members": {"type": "int"}, "maxlen": 512},
            "[3,4,7,2,1]",
        ),
        (
            np.array([(300, "accelerating")], dtype=[("e0", np.int32), ("e1", "<U512")]),
            {"type": "tuple", "members": [{"type": "int"}, {"type": "string"}]},
            '[300,"accelerating"]',
        ),
        (
            np.array([(300, "accelerating")], dtype=[("e0", np.int32), ("e1", "<U512")]),
            {"type": "struct", "members": {"e0": {"type": "int"}, "e1": {"type": "string"}}},
            '{"e0":300,"e1":"accelerating"}',
        ),
        (
            np.array([[1, 2], [3, 4], [5, 6]], dtype="<f4"),
            {"type": "matrix", "elementtype": "<f4", "names": ["x", "y"], "maxlen": [100, 100]},
            '{"len":[2,3],"blob":"AACAPwAAAEAAAEBAAACAQAAAoEAAAMBA"}',
        ),
    ],
)
def test_encode(decoded, datainfo, encoded):
    assert encode(decoded, datainfo) == encoded


@pytest.mark.parametrize(
    ("decoded", "datainfo", "encoded"),
    [
        (1.23, {"type": "double"}, "1.23"),
        (125.5, {"type": "scaled", "scale": 0.1}, "1255"),
        (42, {"type": "int"}, "42"),
        (True, {"type": "bool"}, "true"),
        (DummyEnum.TWO, {"type": "enum", "members": {"ONE": 1, "TWO": 2, "THREE": 3}}, "2"),
        ("hello", {"type": "string"}, '"hello"'),
        (np.frombuffer(b"\0", dtype=np.uint8), {"type": "blob", "maxbytes": 512}, '"AA=="'),
        (np.frombuffer(b"SECoP", dtype=np.uint8), {"type": "blob", "maxbytes": 512}, '"U0VDb1A="'),
        (
            np.array([3, 4, 7, 2, 1], dtype=np.int32),
            {"type": "array", "members": {"type": "int"}, "maxlen": 512},
            "[3,4,7,2,1]",
        ),
        (
            np.array([(300, "accelerating")], dtype=[("e0", np.int32), ("e1", "<U512")]),
            {"type": "tuple", "members": [{"type": "int"}, {"type": "string"}]},
            '[300,"accelerating"]',
        ),
        (
            np.array([(300, "accelerating")], dtype=[("e0", np.int32), ("e1", "<U512")]),
            {"type": "struct", "members": {"e0": {"type": "int"}, "e1": {"type": "string"}}},
            '{"e0":300,"e1":"accelerating"}',
        ),
        (
            np.array([[1, 2], [3, 4], [5, 6]], dtype="<f4"),
            {"type": "matrix", "elementtype": "<f4", "names": ["x", "y"], "maxlen": [100, 100]},
            '{"len":[2,3],"blob":"AACAPwAAAEAAAEBAAACAQAAAoEAAAMBA"}',
        ),
    ],
)
def test_decode(decoded, datainfo, encoded):
    result = decode(f"[{encoded}]", datainfo, AttrRW(secop_datainfo_to_fastcs_dtype(datainfo)))
    if isinstance(decoded, np.ndarray):
        np.testing.assert_array_equal(result, decoded)
    elif isinstance(decoded, enum.Enum):
        assert result.name == decoded.name
        assert result.value == decoded.value
    else:
        assert result == decoded


def test_encode_unknown_type():
    with pytest.raises(SecopError):
        encode(5, {"type": "some_random_type_that_doesn't exist"})


@pytest.mark.parametrize(
    ("io_cls", "expected"),
    [
        (SecopAttributeIO, 123.456),
        (SecopRawAttributeIO, "123.456"),
    ],
)
async def test_attribute_io_update(io_cls, expected):
    connection = AsyncMock(spec=IPConnection)
    attr = AsyncMock(spec=AttrRW)
    io = io_cls(connection=connection)

    with (
        patch("fastcs_secop._io.secop_read", return_value='[123.456, {"t": 5, "e": 7}]'),
        patch("fastcs_secop._io.decode", return_value=123.456),
    ):
        await io.update(attr)

    attr.update.assert_awaited_once_with(expected)


@pytest.mark.parametrize(
    ("io_cls", "error"),
    [
        (SecopAttributeIO, SecopError),
        (SecopAttributeIO, ConnectionError),
        (SecopRawAttributeIO, SecopError),
        (SecopRawAttributeIO, ConnectionError),
    ],
)
async def test_attribute_io_update_fails(io_cls, error):
    connection = AsyncMock(spec=IPConnection)
    attr = AsyncMock(spec=AttrRW)
    io = io_cls(connection=connection)

    with patch("fastcs_secop._io.secop_read", side_effect=error):
        await io.update(attr)


@pytest.mark.parametrize(
    ("io_cls", "expected"),
    [
        (SecopAttributeIO, 123.456),
        (SecopRawAttributeIO, "123.456"),
    ],
)
async def test_attribute_io_send(io_cls, expected):
    connection = AsyncMock(spec=IPConnection)
    attr = AsyncMock(spec=AttrRW)
    io = io_cls(connection=connection)

    with (
        patch("fastcs_secop._io.secop_change") as mock_change,
        patch("fastcs_secop._io.encode", return_value="123.456"),
    ):
        await io.send(attr, 123.456)

    mock_change.assert_awaited_once()


@pytest.mark.parametrize(
    ("io_cls", "error"),
    [
        (SecopAttributeIO, SecopError),
        (SecopAttributeIO, ConnectionError),
        (SecopRawAttributeIO, SecopError),
        (SecopRawAttributeIO, ConnectionError),
    ],
)
async def test_attribute_io_send_fails(io_cls, error):
    connection = AsyncMock(spec=IPConnection)
    attr = AsyncMock(spec=AttrRW)
    io = io_cls(connection=connection)

    with (
        patch("fastcs_secop._io.secop_change", side_effect=error),
        patch("fastcs_secop._io.encode", return_value="123.456"),
    ):
        await io.send(attr, 123.456)
