"""FastCS controllers for SECoP nodes."""

import typing
import uuid
from logging import getLogger

import orjson
from fastcs.attributes import AttrR, AttrRW
from fastcs.connections import IPConnection, IPConnectionSettings
from fastcs.controllers import Controller
from fastcs.methods import command, scan

from fastcs_secop._io import (
    SecopAttributeIO,
    SecopAttributeIORef,
    SecopRawAttributeIO,
    SecopRawAttributeIORef,
    decode,
    encode,
)
from fastcs_secop._util import SecopError, SecopQuirks, is_raw, secop_datainfo_to_fastcs_dtype

logger = getLogger(__name__)


class SecopCommandController(Controller):
    """SECoP command controller."""

    def __init__(
        self,
        *,
        connection: IPConnection,
        module_name: str,
        command_name: str,
        datainfo: dict[str, typing.Any],
        quirks: SecopQuirks,
    ) -> None:
        """Subcontroller for a SECoP command.

        This class is automatically added as a subcontroller by
        :py:obj:`SecopModuleController` for command-type parameters.

        Args:
            connection: The connection to use.
            module_name: The module in which this command is defined.
            command_name: The name of the command.
            datainfo: The datainfo dictionary for this command.
            quirks: The quirks configuration (see :py:obj:`~fastcs_secop.SecopQuirks`).

        """
        super().__init__()

        self._connection = connection
        self._module_name = module_name
        self._command_name = command_name
        self._datainfo = datainfo
        self._quirks = quirks

        self.raw_args = self._datainfo.get("argument") is not None and is_raw(
            self._module_name, self._command_name, self._datainfo["argument"], self._quirks
        )
        self.raw_result = self._datainfo.get("result") is not None and is_raw(
            self._module_name, self._command_name, self._datainfo["result"], self._quirks
        )

    async def initialise(self) -> None:
        """Initialise the command controller.

        This will set up PVs for ``Args`` and ``Result`` (if they have a type).
        """
        if self._datainfo.get("argument") is not None:
            args_type = secop_datainfo_to_fastcs_dtype(
                self._datainfo["argument"], raw=self.raw_args
            )
        else:
            args_type = None

        if self._datainfo.get("result") is not None:
            result_type = secop_datainfo_to_fastcs_dtype(
                self._datainfo["result"], raw=self.raw_result
            )
        else:
            result_type = None

        if args_type is not None:
            self.args = AttrRW(description="args", datatype=args_type)
        else:
            self.args = None

        if result_type is not None:
            self.result = AttrR(description="result", datatype=result_type)
        else:
            self.result = None

    @command()
    async def execute(self) -> None:
        """Execute the command."""
        try:
            prefix = f"do {self._module_name}:{self._command_name}"
            response_prefix = f"done {self._module_name}:{self._command_name}"

            if self.args is not None:
                if self.raw_args:
                    cmd = f"{prefix} {self.args.get()}\n"
                else:
                    cmd = f"{prefix} {encode(self.args.get(), self._datainfo['argument'])}\n"
            else:
                cmd = f"{prefix}\n"

            logger.debug("Sending command: '%s'", cmd)
            response = await self._connection.send_query(cmd)
            logger.debug("Response: '%s'", response)

            response = response.strip()
            if not response.startswith(response_prefix):
                logger.error("command '%s' failed (response='%s')", prefix, response)
                return

            response = response[len(response_prefix) :].strip()

            if self.result is not None:
                if self.raw_result:
                    await self.result.update(orjson.dumps(orjson.loads(response)[0]).decode())
                else:
                    await self.result.update(
                        decode(response, self._datainfo["result"], self.result)
                    )
        except Exception as e:
            logger.error(
                "command %s:%s failed: %s: %s",
                self._module_name,
                self._command_name,
                e.__class__.__name__,
                e,
            )


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

        This class is automatically added as a subcontroller by
        :py:obj:`SecopController` for each present SECoP module.

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
        self._connection = connection

        super().__init__(
            ios=[
                SecopAttributeIO(connection=connection),
                SecopRawAttributeIO(connection=connection),
            ]
        )

    async def initialise(self) -> None:
        """Create attributes for all accessibles in this SECoP module."""
        for parameter_name, parameter in self._module["accessibles"].items():
            if (self._module_name, parameter_name) in self._quirks.skip_accessibles:
                continue

            logger.debug("Creating attribute for parameter %s", parameter_name)
            datainfo = parameter["datainfo"]

            description = parameter.get("description", "")[: self._quirks.max_description_length]

            attr_cls = AttrR if parameter.get("readonly", False) else AttrRW

            raw = is_raw(self._module_name, parameter_name, datainfo, self._quirks)

            if raw:
                io_ref = SecopRawAttributeIORef(
                    module_name=self._module_name,
                    accessible_name=parameter_name,
                    update_period=self._quirks.update_period,
                )
            else:
                io_ref = SecopAttributeIORef(
                    module_name=self._module_name,
                    accessible_name=parameter_name,
                    update_period=self._quirks.update_period,
                    datainfo=datainfo,
                )

            if datainfo["type"] == "command":
                command_controller = SecopCommandController(
                    module_name=self._module_name,
                    command_name=parameter_name,
                    connection=self._connection,
                    datainfo=datainfo,
                    quirks=self._quirks,
                )
                self.add_sub_controller(parameter_name, command_controller)
                await command_controller.initialise()
            else:
                fastcs_type = secop_datainfo_to_fastcs_dtype(datainfo=datainfo, raw=raw)

                self.add_attribute(
                    parameter_name,
                    attr_cls(
                        fastcs_type,
                        io_ref=io_ref,
                        description=description,
                    ),
                )


class SecopController(Controller):
    """FastCS Controller for a SECoP node."""

    def __init__(self, settings: IPConnectionSettings, quirks: SecopQuirks | None = None) -> None:
        """FastCS Controller for a SECoP node.

        The intended usage is via :py:obj:`fastcs.control_system.FastCS`:

        .. code-block:: python

            from fastcs_secop import SecopController, SecopQuirks
            from fastcs.control_system import FastCS

            controller = SecopController(
                settings=IPConnectionSettings(ip="127.0.0.1", port=1234),
                quirks=SecopQuirks(...),
            )

            transports = [...]

            fastcs = FastCS(
                controller,
                transports,
            )
            fastcs.run()

        See Also:
            :ref:`example_ca_ioc` and :ref:`example_pva_ioc` for examples of full configurations

        Args:
            settings: The communication settings (e.g. IP address, port) at which
                the SECoP node is reachable.
            quirks: :py:obj:`~fastcs_secop.SecopQuirks` that affects how attributes are processed.

        """
        self._ip_settings = settings
        self._connection = IPConnection()
        self._quirks = quirks or SecopQuirks()

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

        try:
            manufacturer, product, _, _ = identification.split(",")
        except ValueError as e:
            raise SecopError("Invalid response to '*IDN?'") from e

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

        logger.info("Connected to SECoP device with IDN='%s'.", identification)

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
        await self._create_modules()

    async def _create_modules(self) -> None:
        """Create subcontrollers for each SECoP module."""
        descriptor = await self._connection.send_query("describe\n")
        if not descriptor.startswith("describing . "):
            raise SecopError(f"Invalid response to 'describe': '{descriptor}'.")

        descriptor = orjson.loads(descriptor[len("describing . ") :])

        description = descriptor["description"]
        equipment_id = descriptor["equipment_id"]

        logger.info("SECoP equipment_id = '%s', description = '%s'", equipment_id, description)
        logger.debug(
            "descriptor = %s", orjson.dumps(descriptor, option=orjson.OPT_INDENT_2).decode()
        )

        modules = descriptor["modules"]

        for module_name, module in modules.items():
            if module_name in self._quirks.skip_modules:
                continue
            logger.debug("Creating subcontroller for module %s", module_name)
            module_controller = SecopModuleController(
                connection=self._connection,
                module_name=module_name,
                module=module,
                quirks=self._quirks,
            )
            await module_controller.initialise()
            self.add_sub_controller(name=module_name, sub_controller=module_controller)
