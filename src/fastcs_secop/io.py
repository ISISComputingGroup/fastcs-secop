"""Implementation of IO for SECoP accessibles."""

import base64
import json
from dataclasses import dataclass, field
from enum import Enum
from logging import getLogger
from typing import Any, TypeAlias, cast

import numpy as np
import numpy.typing as npt
from fastcs.attributes import AttributeIO, AttributeIORef, AttrR, AttrW
from fastcs.connections import IPConnection

from fastcs_secop._util import (
    SecopError,
    secop_dtype_to_numpy_dtype,
    struct_structured_dtype,
    tuple_structured_dtype,
)

logger = getLogger(__name__)


T: TypeAlias = int | float | str | bool | Enum | npt.NDArray[Any]
"""Generic type parameter for SECoP IO."""


async def secop_read(connection: IPConnection, module_name: str, accessible_name: str) -> str:
    """Read a SECoP accessible.

    Args:
        connection: Connection reference,
        module_name: Module name
        accessible_name: Accessible name

    Returns:
        The result of reading from the accessible, after calling :py:obj:`json.loads`.

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


class SecopAttributeIO(AttributeIO[T, SecopAttributeIORef]):
    """IO for a SECoP parameter of any type other than 'command'."""

    def __init__(self, *, connection: IPConnection) -> None:
        """IO for a SECoP parameter of any type other than 'command'."""
        super().__init__()

        self._connection = connection

    def decode(self, value: str, datainfo: dict[str, Any], attr: AttrR[T]) -> T:  # noqa ANN401
        """Decode the transported value into a python datatype.

        Args:
            value: The value to decode (the raw transported string)
            datainfo: The SECoP ``datainfo`` dictionary for this attribute.

        Returns:
            Python datatype representation of the transported value.

        """
        value, *_ = json.loads(value)
        match datainfo["type"]:
            case "int" | "bool" | "double" | "string":
                return value
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
            case _:
                raise SecopError(f"Cannot handle SECoP dtype '{datainfo['type']}'")

    def encode(self, value: T, datainfo: dict[str, Any]) -> str:
        """Encode the transported value to a string for transport.

        Args:
            value: The value to encode.
            datainfo: The SECoP ``datainfo`` dictionary for this attribute.

        """
        match datainfo["type"]:
            case "int" | "bool" | "double" | "string" | "enum":
                return json.dumps(value)
            case "scaled":
                return json.dumps(round(value / datainfo["scale"]))
            case "blob":
                assert isinstance(value, np.ndarray)
                return json.dumps(base64.b64encode("".join(chr(c) for c in value).encode("utf-8")))
            case "array" | "tuple":
                assert isinstance(value, np.ndarray)
                return json.dumps(value.tolist())
            case _:
                raise SecopError(f"Cannot handle SECoP dtype '{datainfo['type']}'")

    async def update(self, attr: AttrR[T, SecopAttributeIORef]) -> None:
        """Read value from device and update the value in FastCS."""
        try:
            raw_value = await secop_read(
                self._connection, attr.io_ref.module_name, attr.io_ref.accessible_name
            )
            value = self.decode(raw_value, attr.io_ref.datainfo, attr)
            await attr.update(value)
        except ConnectionError:
            # Reconnect will be attempted in a periodic scan task
            pass
        except Exception:
            logger.exception("Exception during update()")

    async def send(self, attr: AttrW[T, SecopAttributeIORef], value: T) -> None:
        """Send a value from FastCS to the device."""
        try:
            encoded_value = self.encode(value, attr.io_ref.datainfo)
            await secop_change(
                self._connection,
                attr.io_ref.module_name,
                attr.io_ref.accessible_name,
                encoded_value,
            )
        except ConnectionError:
            # Reconnect will be attempted in a periodic scan task
            pass
        except Exception:
            logger.exception("Exception during send()")


class SecopRawAttributeIO(AttributeIO[str, SecopRawAttributeIORef]):
    """Raw IO for a SECoP parameter of any type other than 'command'.

    For "raw" IO, no serialization/deserialization is performed. All values are transmitted
    to/from FastCS as strings. It is up to the client to interpret those strings correctly.

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
            await attr.update(raw_value)
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
        except ConnectionError:
            # Reconnect will be attempted in a periodic scan task
            pass
        except Exception:
            logger.exception("Exception during send()")
