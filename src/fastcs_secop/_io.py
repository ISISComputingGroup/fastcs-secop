"""Implementation of IO for SECoP accessibles."""

import base64
import enum
from dataclasses import dataclass, field
from enum import Enum
from logging import getLogger
from typing import Any, TypeAlias, cast

import numpy as np
import numpy.typing as npt
import orjson
from fastcs.attributes import AttributeIO, AttributeIORef, AttrR, AttrW
from fastcs.connections import IPConnection

from fastcs_secop._util import (
    SecopError,
    secop_dtype_to_numpy_dtype,
    struct_structured_dtype,
    tuple_structured_dtype,
)

logger = getLogger(__name__)


T: TypeAlias = int | float | str | bool | Enum | npt.NDArray[Any]  # noqa: UP040 (sphinx doesn't like it)
"""Generic type parameter for SECoP IO."""


async def secop_read(connection: IPConnection, module_name: str, accessible_name: str) -> str:
    """Read a SECoP accessible.

    Args:
        connection: Connection reference,
        module_name: Module name
        accessible_name: Accessible name

    Returns:
        The result of reading from the accessible, after JSON deserialisation.

    Raises:
        SecopError: If a valid response was not received

    """
    query = f"read {module_name}:{accessible_name}\n"
    response = await connection.send_query(query)
    response = response.strip()

    prefix = f"reply {module_name}:{accessible_name} "
    if not response.startswith(prefix):
        raise SecopError(f"Invalid response to 'read' command by SECoP device: '{response}'")

    return response[len(prefix) :]


async def secop_change(
    connection: IPConnection, module_name: str, accessible_name: str, encoded_value: str
) -> None:
    """Change a SECoP accessible.

    Args:
        connection: Connection reference,
        module_name: Module name
        accessible_name: Accessible name
        encoded_value: Value to set (as a raw string ready for transport).

    Raises:
        SecopError: If a valid response was not received

    """
    query = f"change {module_name}:{accessible_name} {encoded_value}\n"

    response = await connection.send_query(query)
    response = response.strip()

    prefix = f"changed {module_name}:{accessible_name} "

    if not response.startswith(prefix):
        raise SecopError(f"Invalid response to 'change' command by SECoP device: '{response}'")


@dataclass
class SecopAttributeIORef(AttributeIORef):
    """AttributeIO parameters for a SECoP parameter (accessible)."""

    module_name: str = ""
    accessible_name: str = ""
    datainfo: dict[str, Any] = field(default_factory=dict)


@dataclass
class SecopRawAttributeIORef(AttributeIORef):
    """RawAttributeIO parameters for a SECoP parameter (accessible)."""

    module_name: str = ""
    accessible_name: str = ""


def decode(raw_value: str, datainfo: dict[str, Any], attr: AttrR[T]) -> T:  # noqa ANN401
    """Decode the transported value into a python datatype.

    Args:
        value: The value to decode (the raw transported string)
        datainfo: The SECoP ``datainfo`` dictionary for this attribute.

    Returns:
        Python datatype representation of the transported value.

    """
    value, *_ = orjson.loads(raw_value)
    match datainfo["type"]:
        case "enum":
            return attr.dtype(cast(int, value))
        case "scaled":
            return value * datainfo["scale"]
        case "blob":
            return np.frombuffer(base64.b64decode(value), dtype=np.uint8)
        case "array":
            inner_np_dtype = secop_dtype_to_numpy_dtype(datainfo["members"])
            return np.array(value, dtype=inner_np_dtype)
        case "tuple":
            structured_np_dtype = tuple_structured_dtype(datainfo)
            return np.array([tuple(value)], dtype=structured_np_dtype)
        case "struct":
            structured_np_dtype = struct_structured_dtype(datainfo)
            arr = np.zeros(shape=(1,), dtype=structured_np_dtype)
            for k, v in cast(dict[str, Any], value).items():
                arr[0][k] = v
            return arr
        case "matrix":
            lengths = value["len"][::-1]
            return np.frombuffer(
                base64.b64decode(value["blob"]), dtype=datainfo["elementtype"]
            ).reshape(lengths)
        case _:
            return value


def encode(value: T, datainfo: dict[str, Any]) -> str:
    """Encode the transported value to a string for transport.

    Args:
        value: The value to encode.
        datainfo: The SECoP ``datainfo`` dictionary for this attribute.

    """
    match datainfo["type"]:
        case "int" | "bool" | "double" | "string":
            return orjson.dumps(value).decode()
        case "enum":
            assert isinstance(value, enum.Enum)
            return orjson.dumps(value.value).decode()
        case "scaled":
            val = round(value / datainfo["scale"])
            assert isinstance(val, int)
            return orjson.dumps(val).decode()
        case "blob":
            assert isinstance(value, np.ndarray)
            return orjson.dumps(base64.b64encode(value.tobytes()).decode()).decode()
        case "array":
            return orjson.dumps(value, option=orjson.OPT_SERIALIZE_NUMPY).decode()
        case "tuple":
            assert isinstance(value, np.ndarray)
            return orjson.dumps(value.tolist()[0]).decode()
        case "struct":
            assert isinstance(value, np.ndarray)
            ans = {}
            assert value.dtype.names is not None
            for name in value.dtype.names:
                ans[name] = value[name][0]
            return orjson.dumps(ans, option=orjson.OPT_SERIALIZE_NUMPY).decode()
        case "matrix":
            assert isinstance(value, np.ndarray)
            return orjson.dumps(
                {"len": value.shape[::-1], "blob": base64.b64encode(value.tobytes()).decode()}
            ).decode()
        case _:
            raise SecopError(f"Cannot handle SECoP dtype '{datainfo['type']}'")


class SecopAttributeIO(AttributeIO[T, SecopAttributeIORef]):
    """IO for a SECoP parameter of any type other than 'command'."""

    def __init__(self, *, connection: IPConnection) -> None:
        """IO for a SECoP parameter of any type other than 'command'."""
        super().__init__()

        self._connection = connection

    async def update(self, attr: AttrR[T, SecopAttributeIORef]) -> None:
        """Read value from device and update the value in FastCS."""
        try:
            raw_value = await secop_read(
                self._connection, attr.io_ref.module_name, attr.io_ref.accessible_name
            )
            value = decode(raw_value, attr.io_ref.datainfo, attr)
            await attr.update(value)
        except ConnectionError:
            # Reconnect will be attempted in a periodic scan task
            pass
        except Exception:
            logger.exception("Exception during update()")

    async def send(self, attr: AttrW[T, SecopAttributeIORef], value: T) -> None:
        """Send a value from FastCS to the device."""
        try:
            encoded_value = encode(value, attr.io_ref.datainfo)
            await secop_change(
                self._connection,
                attr.io_ref.module_name,
                attr.io_ref.accessible_name,
                encoded_value,
            )
            # Ugly, but I can't find a public alternative...
            # https://github.com/DiamondLightSource/FastCS/pull/292
            await attr._call_sync_setpoint_callbacks(value)  # noqa: SLF001
        except ConnectionError:
            # Reconnect will be attempted in a periodic scan task
            pass
        except Exception as e:
            logger.error("Exception during send() for %s: %s: %s", attr, e.__class__.__name__, e)


class SecopRawAttributeIO(AttributeIO[str, SecopRawAttributeIORef]):
    """Raw IO for a SECoP parameter of any type other than 'command'.

    For "raw" IO, all values are transmitted to/from FastCS as strings.
    It is up to the client to interpret those strings correctly.

    This is intended as a fallback mode for transports which cannot represent complex
    data types.

    """

    def __init__(self, *, connection: IPConnection) -> None:
        """IO for a SECoP parameter of any type other than 'command'."""
        super().__init__()

        self._connection = connection

    async def update(self, attr: AttrR[str, SecopRawAttributeIORef]) -> None:
        """Read value from device and update the value in FastCS."""
        try:
            raw_value = await secop_read(
                self._connection, attr.io_ref.module_name, attr.io_ref.accessible_name
            )
            # Get rid of timestamp and other specifiers, we just want the value
            value, *_ = orjson.loads(raw_value)
            await attr.update(orjson.dumps(value).decode())
        except ConnectionError:
            # Reconnect will be attempted in a periodic scan task
            pass
        except Exception:
            logger.exception("Exception during update()")

    async def send(self, attr: AttrW[str, SecopRawAttributeIORef], value: str) -> None:
        """Send a value from FastCS to the device."""
        try:
            await secop_change(
                self._connection,
                attr.io_ref.module_name,
                attr.io_ref.accessible_name,
                value,
            )
            # Ugly, but I can't find a public alternative...
            # https://github.com/DiamondLightSource/FastCS/pull/292
            await attr._call_sync_setpoint_callbacks(value)  # noqa: SLF001
        except ConnectionError:
            # Reconnect will be attempted in a periodic scan task
            pass
        except Exception:
            logger.exception("Exception during send()")
