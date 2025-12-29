"""FastCS controllers for SECoP nodes."""

import enum
import json
import typing
import uuid
from logging import getLogger

import numpy as np
from fastcs.attributes import AttrR, AttrRW
from fastcs.connections import IPConnection, IPConnectionSettings
from fastcs.controllers import Controller
from fastcs.datatypes import Bool, Enum, Float, Int, String, Table, Waveform
from fastcs.methods import scan

from fastcs_secop import SecopQuirks
from fastcs_secop._util import SecopError, format_string_to_prec, struct_structured_dtype
from fastcs_secop.io import (
    SecopAttributeIO,
    SecopAttributeIORef,
    SecopRawAttributeIO,
    SecopRawAttributeIORef,
    secop_dtype_to_numpy_dtype,
    tuple_structured_dtype,
)

logger = getLogger(__name__)


class SecopModuleController(Controller):
    """FastCS controller for a SECoP module."""

    def __init__(
        self,
        *,
        connection: IPConnection,
        module_name: str,
        module: dict[str, typing.Any],
        quirks: SecopQuirks,
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
            quirks: Affects how attributes are processed.
                See :py:obj:`~fastcs_secop.SecopQuirks` for details.

        """
        self._module_name = module_name
        self._module = module
        self._quirks = quirks
        super().__init__(
            ios=[
                SecopAttributeIO(connection=connection),
                SecopRawAttributeIO(connection=connection),
            ]
        )

    async def initialise(self) -> None:  # noqa PLR0912 TODO
        """Create attributes for all accessibles in this SECoP module."""
        for parameter_name, parameter in self._module["accessibles"].items():
            if (self._module_name, parameter_name) in self._quirks.skip_accessibles:
                continue

            logger.debug("Creating attribute for parameter %s", parameter_name)
            datainfo = parameter["datainfo"]
            secop_dtype = datainfo["type"]

            min_val = datainfo.get("min")
            max_val = datainfo.get("max")
            scale = datainfo.get("scale")

            description = parameter.get("description", "")[: self._quirks.max_description_length]

            attr_cls = AttrR if parameter.get("readonly", False) else AttrRW

            io_ref = SecopAttributeIORef(
                module_name=self._module_name,
                accessible_name=parameter_name,
                update_period=self._quirks.update_period,
                datainfo=datainfo,
            )

            raw_io_ref = SecopRawAttributeIORef(
                module_name=self._module_name,
                accessible_name=parameter_name,
                update_period=self._quirks.update_period,
            )

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
                    attr_cls(
                        Float(
                            units=datainfo.get("unit", None),
                            min_alarm=min_val,
                            max_alarm=max_val,
                            prec=format_string_to_prec(datainfo.get("fmtstr", None)) or 6,
                        ),
                        io_ref=io_ref,
                        description=description,
                    ),
                )
            elif secop_dtype == "int":
                self.add_attribute(
                    parameter_name,
                    attr_cls(
                        Int(
                            units=datainfo.get("unit", None),
                            min_alarm=min_val,
                            max_alarm=max_val,
                        ),
                        io_ref=io_ref,
                        description=description,
                    ),
                )
            elif secop_dtype == "bool":
                self.add_attribute(
                    parameter_name,
                    attr_cls(
                        Bool(),
                        io_ref=io_ref,
                        description=description,
                    ),
                )
            elif secop_dtype == "enum":
                enum_type = enum.Enum("enum_type", datainfo["members"])

                self.add_attribute(
                    parameter_name,
                    attr_cls(
                        Enum(enum_type),
                        io_ref=io_ref,
                        description=description,
                    ),
                )
            elif secop_dtype == "string":
                self.add_attribute(
                    parameter_name,
                    attr_cls(
                        String(),
                        io_ref=io_ref,
                        description=description,
                    ),
                )
            elif secop_dtype == "blob":
                self.add_attribute(
                    parameter_name,
                    attr_cls(
                        Waveform(np.uint8, shape=(datainfo["maxbytes"],)),
                        io_ref=io_ref,
                        description=description,
                    ),
                )
            elif secop_dtype == "array":
                if (
                    self._quirks.raw_array
                    or (self._module_name, parameter_name) in self._quirks.raw_accessibles
                ):
                    self.add_attribute(
                        parameter_name,
                        attr_cls(
                            String(65536),
                            io_ref=raw_io_ref,
                            description=description,
                        ),
                    )
                else:
                    inner_dtype = datainfo["members"]
                    np_inner_dtype = secop_dtype_to_numpy_dtype(inner_dtype)

                    self.add_attribute(
                        parameter_name,
                        attr_cls(
                            Waveform(np_inner_dtype, shape=(datainfo["maxlen"],)),
                            io_ref=io_ref,
                            description=description,
                        ),
                    )
            elif secop_dtype == "tuple":
                if (
                    self._quirks.raw_tuple
                    or (self._module_name, parameter_name) in self._quirks.raw_accessibles
                ):
                    self.add_attribute(
                        parameter_name,
                        attr_cls(
                            String(65536),
                            io_ref=raw_io_ref,
                            description=description,
                        ),
                    )
                else:
                    structured_dtype = tuple_structured_dtype(datainfo)

                    self.add_attribute(
                        parameter_name,
                        attr_cls(
                            Table(structured_dtype),
                            io_ref=io_ref,
                            description=description,
                        ),
                    )
            elif secop_dtype == "struct":
                if (
                    self._quirks.raw_struct
                    or (self._module_name, parameter_name) in self._quirks.raw_accessibles
                ):
                    self.add_attribute(
                        parameter_name,
                        attr_cls(
                            String(65536),
                            io_ref=raw_io_ref,
                            description=description,
                        ),
                    )
                else:
                    structured_dtype = struct_structured_dtype(datainfo)

                    self.add_attribute(
                        parameter_name,
                        attr_cls(
                            Table(structured_dtype),
                            io_ref=io_ref,
                            description=description,
                        ),
                    )
            else:
                raise SecopError(f"Unsupported secop data type '{secop_dtype}")


class SecopController(Controller):
    """FastCS Controller for a SECoP node."""

    def __init__(self, settings: IPConnectionSettings, quirks: SecopQuirks | None = None) -> None:
        """FastCS Controller for a SECoP node.

        Args:
            settings: The communication settings (e.g. IP address, port) at which
                the SECoP node is reachable.
            quirks: :py:obj:`dict`-like object of :py:obj:`~fastcs_secop.SecopQuirks`
                that affects how attributes are processed.

        """
        self._ip_settings = settings
        self._connection = IPConnection()
        self.quirks = quirks or SecopQuirks()

        super().__init__()

    async def connect(self) -> None:
        """Connect to the SECoP node."""
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

        logger.info("SECoP equipment_id = '%s', description = '%s'", equipment_id, description)
        logger.debug("descriptor = %s", json.dumps(descriptor, indent=2))

        modules = descriptor["modules"]

        for module_name, module in modules.items():
            if module_name in self.quirks.skip_modules:
                continue
            logger.debug("Creating subcontroller for module %s", module_name)
            module_controller = SecopModuleController(
                connection=self._connection,
                module_name=module_name,
                module=module,
                quirks=self.quirks,
            )
            await module_controller.initialise()
            self.add_sub_controller(name=module_name, sub_controller=module_controller)
