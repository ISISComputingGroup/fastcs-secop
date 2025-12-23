import json
import typing
from dataclasses import dataclass
from logging import getLogger

from fastcs.attributes import AttributeIO, AttributeIORef, AttrR, AttrW
from fastcs.connections import IPConnection

from fastcs_secop._util import SecopError

logger = getLogger(__name__)

NumberT = typing.TypeVar("NumberT", int, float)


@dataclass
class SecopAttributeIORef(AttributeIORef):
    module_name: str = ""
    accessible_name: str = ""
    decode: typing.Callable[[typing.Any], typing.Any] = lambda x: x
    encode: typing.Callable[[typing.Any], typing.Any] = lambda x: x


class SecopAttributeIO(AttributeIO[NumberT, SecopAttributeIORef]):
    def __init__(self, *, connection: IPConnection) -> None:
        super().__init__()

        self._connection = connection

    async def update(self, attr: AttrR[NumberT, SecopAttributeIORef]) -> None:
        """Read value from device and update the value in FastCS."""
        try:
            query = f"read {attr.io_ref.module_name}:{attr.io_ref.accessible_name}\n"
            response = await self._connection.send_query(query)
            response = response.strip()

            prefix = f"reply {attr.io_ref.module_name}:{attr.io_ref.accessible_name} "
            if not response.startswith(prefix):
                raise SecopError(
                    f"Invalid response to 'read' command by SECoP device: '{response}'"
                )

            value = json.loads(response[len(prefix) :])[0]
            value = attr.io_ref.decode(value)
            await attr.update(value)
        except ConnectionError:
            # Reconnect will be attempted in a periodic scan task
            pass
        except Exception:
            logger.exception("Exception during update()")

    async def send(self, attr: AttrW[NumberT, SecopAttributeIORef], value: NumberT) -> None:
        """Send a value from FastCS to the device."""
        try:
            query = f"change {attr.io_ref.module_name}:{attr.io_ref.accessible_name} {value}\n"

            response = await self._connection.send_query(query)
            response = response.strip()

            prefix = f"changed {attr.io_ref.module_name}:{attr.io_ref.accessible_name} "

            if not response.startswith(prefix):
                raise SecopError(
                    f"Invalid response to 'change' command by SECoP device: '{response}'"
                )
        except ConnectionError:
            # Reconnect will be attempted in a periodic scan task
            pass
        except Exception:
            logger.exception("Exception during update()")
