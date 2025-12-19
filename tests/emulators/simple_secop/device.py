import base64
import time
import typing
from collections import OrderedDict

from lewis.devices import StateMachineDevice

from .states import DefaultState


class Accessible:
    def __init__(self):
        self.description = ""


class Parameter(Accessible):
    def __init__(
        self,
        value,
        *,
        dtype="double",
        unit="",
        prec=3,
        desc="",
        extra_datainfo: dict[str, typing.Any] | None = None,
        value_encoder=lambda x: x,
    ):
        super().__init__()
        self.value = value
        self.dtype = dtype
        self.unit = unit
        self.prec = prec
        self.desc = desc
        self.extra_datainfo = extra_datainfo or {}
        self.value_encoder = value_encoder

    def data_report(self):
        return [
            self.value_encoder(self.value),
            {
                "t": time.time(),
            },
        ]

    def descriptor(self) -> dict[str, typing.Any]:
        return {
            "description": self.desc,
            "datainfo": {
                "type": self.dtype,
                "fmtstr": f"%.{self.prec}f",
                "unit": self.unit,
                **self.extra_datainfo,
            },
            "readonly": False,
        }

    def change(self, value):
        self.value = value


class Command(Accessible):
    def descriptor(self) -> dict[str, typing.Any]:
        return {
            "description": "some_command_description",
            "datainfo": {
                "type": "command",
            },
        }


class OneOfEachDtypeModule:
    def __init__(self):
        self.accessibles = {
            "double": Parameter(
                1.2345, unit="mm", prec=2, desc="a double parameter", dtype="double"
            ),
            "scaled": Parameter(
                42,
                unit="uA",
                prec=4,
                desc="a scaled parameter",
                dtype="scaled",
                extra_datainfo={"scale": 47},
            ),
            "int": Parameter(73, desc="an integer parameter", dtype="int"),
            "bool": Parameter(True, desc="a boolean parameter", dtype="bool"),
            "enum": Parameter(
                1,
                desc="an enum parameter",
                dtype="enum",
                extra_datainfo={
                    "members": {"zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5}
                },
            ),
            "string": Parameter("hello", desc="a string parameter", dtype="string"),
            "blob": Parameter(
                b"a blob of binary data",
                desc="a blob parameter",
                dtype="blob",
                value_encoder=lambda x: base64.b64encode(x).decode("ascii"),
                extra_datainfo={"maxbytes": 512},
            ),
        }

        self.description = "a module with one accessible of each possible dtype"

    def descriptor(self) -> dict[str, typing.Any]:
        return {
            "implementation": __name__,
            "description": self.description,
            "interface_classes": ["Readable"],
            "accessibles": {
                name: accessible.descriptor() for name, accessible in self.accessibles.items()
            },
        }


class SimulatedSecopNode(StateMachineDevice):
    def _initialize_data(self):
        """Initialize the device's attributes."""
        self.modules = {
            "mod1": OneOfEachDtypeModule(),
            "mod2": OneOfEachDtypeModule(),
            "mod3": OneOfEachDtypeModule(),
        }

    def _get_state_handlers(self):
        return {"default": DefaultState()}

    def _get_initial_state(self):
        return "default"

    def _get_transition_handlers(self):
        return OrderedDict([])

    def descriptor(self) -> dict[str, typing.Any]:
        return {
            "equipment_id": "fastcs_secop-lewis-emulator",
            "description": "Simple SECoP emulator",
            "modules": {name: module.descriptor() for name, module in self.modules.items()},
        }
