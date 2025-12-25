import base64
import enum
import json
import typing
import uuid
from logging import getLogger

import numpy as np
import numpy.typing as npt
from fastcs.attributes import AttrRW
from fastcs.connections import IPConnection, IPConnectionSettings
from fastcs.controllers import Controller
from fastcs.datatypes import Bool, Enum, Float, Int, String, Waveform
from fastcs.methods import scan

from fastcs_secop._io import SecopAttributeIO, SecopAttributeIORef
from fastcs_secop._util import SecopError

logger = getLogger(__name__)


def format_string_to_prec(fmt_str: str | None) -> int | None:
    """Convert a SECoP format-string specifier to a precision."""
    if fmt_str is None:
        return None

    if fmt_str.startswith("%.") and fmt_str.endswith("f"):
        return int(fmt_str[2:-1])

    return None


def secop_dtype_to_numpy_dtype(secop_dtype: str) -> npt.DTypeLike:
    if secop_dtype == "double":
        return np.float64
    elif secop_dtype == "int":
        return np.int32
    elif secop_dtype == "bool":
        return np.bool_
    else:
        raise SecopError(f"Cannot handle SECoP dtype '{secop_dtype}' within array/struct/tuple")


class SecopModuleController(Controller):
    def __init__(
        self,
        *,
        connection: IPConnection,
        module_name: str,
        module: dict[str, typing.Any],
    ) -> None:
        """FastCS controller for a SECoP module.

        Instances of this class are added as subcontrollers by
        :py:obj:`SecopController`.

        Args:
            connection: The connection to use.
            module_name: The name of the SECoP module.
            module: A deserialised description, in the
                :external+secop:doc:`SECoP over-the-wire format <specification/descriptive>`,
                of this module.

        """
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
            elif secop_dtype in {"double", "scaled"}:
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
                            decode=lambda x, s=scale: x * s if s is not None else x,
                            encode=lambda x, s=scale: round(x / s) if s is not None else x,
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
                np_inner_dtype = secop_dtype_to_numpy_dtype(inner_dtype)

                def decode(
                    x: list[int | float | bool], t: npt.DTypeLike = np_inner_dtype
                ) -> npt.NDArray[np.int32 | np.float64 | np.bool_]:
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
        """FastCS Controller for a SECoP node.

        Args:
            settings: The communication settings (e.g. IP address, port) at which
                the SECoP node is reachable.

        """
        self._ip_settings = settings
        self._connection = IPConnection()

        super().__init__()

    async def connect(self) -> None:
        await self._connection.connect(self._ip_settings)

    async def deactivate(self) -> None:
        """Turn off asynchronous SECoP communication.

        See :external+secop:doc:`specification/messages/activation` for details.
        """
        await self._connection.send_query("deactivate\n")

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
                await self.deactivate()
                logger.info("Reconnect successful.")
            except Exception:
                logger.info("Reconnect failed.")

    async def check_idn(self) -> None:
        """Verify that the device is a SECoP device.

        This is checked using the SECoP
        :external+secop:doc:`identification message <specification/messages/identification>`.

        Raises:
            SecopError: if the device is not a SECoP device.

        """
        identification = await self._connection.send_query("*IDN?\n")
        identification = identification.strip()

        manufacturer, product, _, _ = identification.split(",")
        if manufacturer not in {
            "ISSE&SINE2020",  # SECOP 1.x
            "ISSE",  # SECOP 2.x
        }:
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
        """Set up FastCS for this SECoP node.

        This introspects the
        :external+secop:doc:`description <specification/messages/description>`
        of the SECoP device to determine the names and contents of the modules
        in this SECoP node.

        A subcontroller of type :py:obj:`SecopModuleController` is added for
        each discovered module.

        This controller attempts to periodically reconnect to the device if the
        connection was closed, and disables asynchronous messages on instantiation.

        Raises:
            SecopError: if the device is not a SECoP device, if a reply in an
                unexpected format is received, or the SECoP node's configuration
                cannot be handled by :py:obj:`fastcs_secop`.

        """
        await self.connect()
        await self.check_idn()
        await self.deactivate()

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
