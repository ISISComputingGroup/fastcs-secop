import json
import logging
import typing
from dataclasses import dataclass
from logging import getLogger

from fastcs.attributes import AttributeIO, AttributeIORef, AttrR, AttrRW, AttrW
from fastcs.connections import IPConnection, IPConnectionSettings
from fastcs.controllers import Controller
from fastcs.datatypes import Bool, Enum, Float, Int, String, Table, Waveform
from fastcs.launch import FastCS
from fastcs.logging import LogLevel, configure_logging
from fastcs.methods import scan
from fastcs.transports import EpicsIOCOptions, EpicsPVATransport
from fastcs.transports.epics.ca import EpicsCATransport

NumberT = typing.TypeVar("NumberT", int, float)


logger = getLogger(__name__)


SECOP_DATATYPES = {
    "double": Float,
    "scaled": Float,  # TODO:
    "int": Int,
    "bool": Bool,
    "enum": Enum,
    "string": String,
    "blob": Waveform,  # TODO: waveform[u8] really
    "array": Waveform,  # TODO: specify generic type
    "tuple": Table,  # Table of anonymous arrays (all of which happen to have length 1)
    "struct": Table,  # Table of named arrays (all of which happen to have length 1)
    "matrix": Waveform,  # Maybe?
    "command": ...,  # Special treatment - it's an AttrX
}


class SecopError(Exception):
    pass


@dataclass
class SecopAttributeIORef(AttributeIORef):
    module_name: str = ""
    accessible_name: str = ""


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

            value = json.loads(response[len(prefix) :])

            await attr.update(attr.dtype(value[0]))
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


class SecopModuleController(Controller):
    def __init__(
        self,
        *,
        connection: IPConnection,
        module_name: str,
        module: dict[str, typing.Any],
    ) -> None:
        self._io = SecopAttributeIO(connection=connection)
        self._module_name = module_name
        self._module = module
        super().__init__(ios=[self._io])

    async def initialise(self) -> None:
        for parameter_name, parameter in self._module["accessibles"].items():
            # secop_dtype = parameter["type"]
            # if secop_dtype == "command":
            #     self.add_attribute()

            self.add_attribute(
                parameter_name,
                AttrRW(
                    Float(),
                    io_ref=SecopAttributeIORef(
                        module_name=self._module_name,
                        accessible_name=parameter_name,
                        update_period=1,
                    ),
                ),
            )


class SecopController(Controller):
    def __init__(self, settings: IPConnectionSettings) -> None:
        self._ip_settings = settings
        self._connection = IPConnection()

        super().__init__()

    async def connect(self) -> None:
        await self._connection.connect(self._ip_settings)

    @scan(15.0)
    async def attempt_reconnect_if_sending_idn_fails(self) -> None:
        try:
            await self._connection.send_query("*IDN?\n")
        except ConnectionError:
            logger.info("Detected connection loss, attempting reconnect.")
            try:
                await self.connect()
                logger.info("Reconnect successful.")
            except Exception:
                logger.info("Reconnect failed.")

    async def check_idn(self) -> None:
        """
        Checks that the response to *IDN? indicates this is a SECoP device.

        Raises:
            ValueError: if device is not a SECoP device.
        """
        identification = await self._connection.send_query("*IDN?\n")
        identification = identification.strip()

        manufacturer, product, draft_date, version = identification.split(",")
        if manufacturer not in [
            "ISSE&SINE2020",  # SECOP 1.x
            "ISSE",  # SECOP 2.x
        ]:
            raise SecopError(
                f"Device responded to '*IDN?' with bad manufacturer string '{manufacturer}'. "
                f"Not a SECoP device?"
            )

        if product != "SECoP":
            raise SecopError(
                f"Device responded to '*IDN?' with bad product string '{product}'. "
                f"Not a SECoP device?"
            )

        print(f"Connected to SECoP device with IDN='{identification}'.")

    async def initialise(self) -> None:
        await self.connect()
        await self.check_idn()

        # Turn off asynchronous replies.
        await self._connection.send_query("deactivate\n")

        descriptor = await self._connection.send_query("describe\n")
        if not descriptor.startswith("describing . "):
            raise SecopError(f"Invalid response to 'describe': '{descriptor}'.")

        descriptor = json.loads(descriptor[len("describing . ") :])

        description = descriptor["description"]
        equipment_id = descriptor["equipment_id"]

        print(f"SECoP equipment_id = '{equipment_id}', description = '{description}'")

        modules = descriptor["modules"]

        for module_name, module in modules.items():
            module_controller = SecopModuleController(
                connection=self._connection,
                module_name=module_name,
                module=module,
            )
            await module_controller.initialise()
            self.add_sub_controller(name=module_name, sub_controller=module_controller)


if __name__ == "__main__":
    configure_logging(level=LogLevel.DEBUG)

    logging.basicConfig(level=LogLevel.DEBUG)

    epics_options = EpicsIOCOptions(pv_prefix="TE:NDW2922:SECOP")
    epics_ca = EpicsCATransport(epicsca=epics_options)
    epics_pva = EpicsPVATransport(epicspva=epics_options)

    fastcs = FastCS(
        SecopController(settings=IPConnectionSettings(ip="127.0.0.1", port=57677)),
        [epics_ca],
    )
    fastcs.run(interactive=True)
