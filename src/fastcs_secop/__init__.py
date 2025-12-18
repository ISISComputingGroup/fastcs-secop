import json
import typing
from dataclasses import dataclass

from fastcs.attributes import Attribute, AttributeIO, AttributeIORef, AttrR, AttrW
from fastcs.connections import IPConnection, IPConnectionSettings
from fastcs.controllers import Controller
from fastcs.datatypes import Float
from fastcs.launch import FastCS
from fastcs.transports import EpicsIOCOptions, EpicsPVATransport
from fastcs.transports.epics.ca import EpicsCATransport

NumberT = typing.TypeVar("NumberT", int, float)


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
        query = f"read {attr.io_ref.module_name}:{attr.io_ref.accessible_name}\n"
        response = await self._connection.send_query(query)
        response = response.strip()

        prefix = f"reply {attr.io_ref.module_name}:{attr.io_ref.accessible_name} "
        if not response.startswith(prefix):
            raise SecopError(f"Invalid response to 'read' command by SECoP device: '{response}")

        value = json.loads(response[len(prefix) :])

        await attr.update(attr.dtype(value[0]))

    async def send(self, attr: AttrW[NumberT, SecopAttributeIORef], value: NumberT) -> None:
        """Send a value from FastCS to the device."""
        raise NotImplementedError()


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

    def parameter_descriptor_to_attribute(
        self,
        module_name: str,
        accessible_name: str,
        parameter_descriptor: dict[str, typing.Any],
    ) -> Attribute:
        return AttrR(
            Float(),
            io_ref=SecopAttributeIORef(
                module_name=module_name,
                accessible_name=accessible_name,
                update_period=0.1,
            ),
        )

    async def initialise(self) -> None:
        for parameter_name, parameter in self._module["accessibles"].items():
            self.add_attribute(
                parameter_name,
                self.parameter_descriptor_to_attribute(
                    module_name=self._module_name,
                    accessible_name=parameter_name,
                    parameter_descriptor=parameter,
                ),
            )


class SecopController(Controller):
    def __init__(self, settings: IPConnectionSettings) -> None:
        self._ip_settings = settings
        self._connection = IPConnection()

        super().__init__()

    async def connect(self) -> None:
        await self._connection.connect(self._ip_settings)

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

        print(f"Connected to SECoP device with IDN='{identification}'")

    async def initialise(self) -> None:
        await self.connect()
        await self.check_idn()

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
    epics_options = EpicsIOCOptions(pv_prefix="TE:NDW2922:SECOP")
    epics_ca = EpicsCATransport(epicsca=epics_options)
    epics_pva = EpicsPVATransport(epicspva=epics_options)

    fastcs = FastCS(
        SecopController(settings=IPConnectionSettings(ip="127.0.0.1", port=57677)),
        [epics_ca],
    )
    fastcs.run()
