import base64
import enum
import json
import logging
import typing
import uuid
from dataclasses import dataclass
from logging import getLogger

import numpy as np
import numpy.typing as npt
from fastcs.attributes import AttributeIO, AttributeIORef, AttrR, AttrRW, AttrW
from fastcs.connections import IPConnection, IPConnectionSettings
from fastcs.controllers import Controller
from fastcs.datatypes import Bool, Enum, Float, Int, String, Waveform
from fastcs.launch import FastCS
from fastcs.logging import LogLevel, configure_logging
from fastcs.methods import scan
from fastcs.transports import EpicsIOCOptions, EpicsPVATransport
from fastcs.transports.epics.ca import EpicsCATransport

NumberT = typing.TypeVar("NumberT", int, float)


logger = getLogger(__name__)


class SecopError(Exception):
    pass


@dataclass
class SecopAttributeIORef(AttributeIORef):
    module_name: str = ""
    accessible_name: str = ""
    decode: callable = lambda x: x
    encode: callable = lambda x: x


def format_string_to_prec(fmt_str: str | None) -> int | None:
    """
    Convert a SECoP format-string specifier to a precision.
    """
    if fmt_str is None:
        return None

    if fmt_str.startswith("%.") and fmt_str.endswith("f"):
        return int(fmt_str[2:-1])

    return None


def secop_dtype_to_numpy_dtype(secop_dtype: str) -> str:
    if secop_dtype == "double":
        return "float64"
    elif secop_dtype == "int":
        return "int32"
    elif secop_dtype == "bool":
        return "int32"
    else:
        raise SecopError(f"Cannot handle SECoP dtype '{secop_dtype}' within array/struct/tuple")


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
            datainfo = parameter["datainfo"]
            secop_dtype = datainfo["type"]

            min_val = datainfo.get("min")
            max_val = datainfo.get("max")
            scale = datainfo.get("scale")

            if secop_dtype == "command":
                # TODO: handle commands
                pass
            elif secop_dtype in ["double", "scaled"]:
                if min_val is not None and scale is not None:
                    min_val *= scale
                if max_val is not None and scale is not None:
                    max_val *= scale

                self.add_attribute(
                    parameter_name,
                    AttrRW(
                        Float(
                            units=datainfo.get("unit", None),
                            min_alarm=min_val,
                            max_alarm=max_val,
                            prec=format_string_to_prec(datainfo.get("fmtstr", None)) or 6,
                        ),
                        io_ref=SecopAttributeIORef(
                            module_name=self._module_name,
                            accessible_name=parameter_name,
                            update_period=1.0,
                            decode=lambda x: x * scale if scale is not None else x,
                            encode=lambda x: int(round(x / scale)) if scale is not None else x,
                        ),
                        description=parameter.get("description", ""),
                    ),
                )
            elif secop_dtype == "int":
                self.add_attribute(
                    parameter_name,
                    AttrRW(
                        Int(
                            units=datainfo.get("unit", None),
                            min_alarm=min_val,
                            max_alarm=max_val,
                        ),
                        io_ref=SecopAttributeIORef(
                            module_name=self._module_name,
                            accessible_name=parameter_name,
                            update_period=1.0,
                        ),
                        description=parameter.get("description", ""),
                    ),
                )
            elif secop_dtype == "bool":
                self.add_attribute(
                    parameter_name,
                    AttrRW(
                        Bool(),
                        io_ref=SecopAttributeIORef(
                            module_name=self._module_name,
                            accessible_name=parameter_name,
                            update_period=1.0,
                        ),
                        description=parameter.get("description", ""),
                    ),
                )
            elif secop_dtype == "enum":
                # TODO: Bug - this doesn't work properly with PVA?
                enum_type = enum.Enum("enum_type", datainfo["members"])

                self.add_attribute(
                    parameter_name,
                    AttrRW(
                        Enum(enum_type),
                        io_ref=SecopAttributeIORef(
                            module_name=self._module_name,
                            accessible_name=parameter_name,
                            update_period=1.0,
                        ),
                        description=parameter.get("description", ""),
                    ),
                )
            elif secop_dtype == "string":
                self.add_attribute(
                    parameter_name,
                    AttrRW(
                        String(),
                        io_ref=SecopAttributeIORef(
                            module_name=self._module_name,
                            accessible_name=parameter_name,
                            update_period=1.0,
                        ),
                        description=parameter.get("description", ""),
                    ),
                )
            elif secop_dtype == "blob":
                self.add_attribute(
                    parameter_name,
                    AttrRW(
                        Waveform(np.uint8, shape=(datainfo["maxbytes"],)),
                        io_ref=SecopAttributeIORef(
                            module_name=self._module_name,
                            accessible_name=parameter_name,
                            update_period=1.0,
                            decode=lambda x: np.frombuffer(base64.b64decode(x), dtype=np.uint8),
                            encode=base64.b64encode,
                        ),
                        description=parameter.get("description", ""),
                    ),
                )
            elif secop_dtype == "array":
                inner_dtype = datainfo["members"]["type"]
                if inner_dtype not in ["double", "int", "bool"]:
                    raise SecopError(f"Cannot handle inner dtype {inner_dtype} in array.")

                np_inner_dtype = secop_dtype_to_numpy_dtype(inner_dtype)

                def decode(x: list[int | float], t: npt.DTypeLike = np_inner_dtype) -> npt.NDArray:
                    return np.array(x, dtype=t)

                self.add_attribute(
                    parameter_name,
                    AttrRW(
                        Waveform(np_inner_dtype, shape=(datainfo["maxlen"],)),
                        io_ref=SecopAttributeIORef(
                            module_name=self._module_name,
                            accessible_name=parameter_name,
                            update_period=1.0,
                            decode=decode,
                        ),
                        description=parameter.get("description", ""),
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
    async def ping(self) -> None:
        """Ping the SECoP device, to check connection is still open.

        Attempts to reconnect if the connection was not open (e.g. closed
        by remote end or network break).
        """
        try:
            token = uuid.uuid4()
            await self._connection.send_query(f"ping {token}\n")
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
