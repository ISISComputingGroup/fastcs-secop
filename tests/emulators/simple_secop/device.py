import base64
import math
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
    def __init__(self, arg_datainfo, result_datainfo):
        super().__init__()
        self.arg_datainfo = arg_datainfo
        self.result_datainfo = result_datainfo

    def descriptor(self) -> dict[str, typing.Any]:
        return {
            "description": "some_command_description",
            "datainfo": {
                "type": "command",
                "argument": self.arg_datainfo,
                "result": self.result_datainfo,
            },
        }


class OneOfEachDtypeModule:
    def __init__(self):
        self.accessibles = {
            "double": Parameter(
                1.2345, unit="mm", prec=4, desc="a double parameter", dtype="double"
            ),
            "scaled": Parameter(
                42,
                unit="uA",
                prec=4,
                desc="a scaled parameter",
                dtype="scaled",
                extra_datainfo={"scale": 47, "min": 0, "max": 1_000_000},
            ),
            "int": Parameter(73, desc="an integer parameter", dtype="int"),
            "bool": Parameter(True, desc="a boolean parameter", dtype="bool"),
            "enum": Parameter(
                3,
                desc="an enum parameter",
                dtype="enum",
                extra_datainfo={"members": {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5}},
            ),
            "string": Parameter("hello", desc="a string parameter", dtype="string"),
            "blob": Parameter(
                b"a blob of binary data",
                desc="a blob parameter",
                dtype="blob",
                value_encoder=lambda x: base64.b64encode(x).decode("ascii"),
                extra_datainfo={"maxbytes": 512},
            ),
            "double_array": Parameter(
                [1.414, 1.618, math.e, math.pi],
                desc="a double array parameter",
                dtype="array",
                extra_datainfo={"maxlen": 512, "members": {"type": "double"}},
            ),
            "int_array": Parameter(
                [1, 1, 2, 3, 5, 8, 13],
                desc="an integer array parameter",
                dtype="array",
                extra_datainfo={"maxlen": 512, "members": {"type": "int"}},
            ),
            "bool_array": Parameter(
                [True, True, False, True, False, False, True, True],
                desc="a bool array parameter",
                dtype="array",
                extra_datainfo={"maxlen": 512, "members": {"type": "bool"}},
            ),
            "enum_array": Parameter(
                [1, 2, 3, 2, 1],
                desc="an enum array parameter",
                dtype="array",
                extra_datainfo={
                    "maxlen": 512,
                    "members": {
                        "type": "enum",
                        "members": {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5},
                    },
                },
            ),
            "tuple": Parameter(
                [1, 5.678, True, "hiya", 5],
                desc="a tuple of int, float, bool",
                dtype="tuple",
                extra_datainfo={
                    "members": [
                        {"type": "int"},
                        {"type": "double"},
                        {"type": "bool"},
                        {"type": "string"},
                        {"type": "enum"},
                    ]
                },
            ),
            "struct": Parameter(
                {"answer": 42, "pi": math.pi, "on_fire": True, "status": "chillin'", "mode": 1},
                desc="a struct of int, float, bool",
                dtype="struct",
                extra_datainfo={
                    "members": {
                        "answer": {"type": "int"},
                        "pi": {"type": "double"},
                        "on_fire": {"type": "bool"},
                        "status": {"type": "string"},
                        "mode": {"type": "enum"},
                    }
                },
            ),
            "matrix": Parameter(
                {"len": [2, 3], "blob": "AACAPwAAAEAAAEBAAACAQAAAoEAAAMBA"},
                desc="a matrix parameter",
                dtype="matrix",
                extra_datainfo={"elementtype": "<f4", "names": ["x", "y"], "maxlen": [100, 100]},
            ),
            "command_bool_int": Command(
                arg_datainfo={"type": "bool"},
                result_datainfo={"type": "int"},
            ),
            "command_null_int": Command(
                arg_datainfo=None,
                result_datainfo={"type": "int"},
            ),
            "command_bool_null": Command(
                arg_datainfo={"type": "bool"},
                result_datainfo=None,
            ),
            "command_null_null": Command(
                arg_datainfo=None,
                result_datainfo=None,
            ),
        }

        self.description = "a module with one accessible of each possible dtype"

    def descriptor(self) -> dict[str, typing.Any]:
        return {
            "implementation": __name__,
            "description": self.description,
            "interface_classes": [],
            "accessibles": {
                name: accessible.descriptor() for name, accessible in self.accessibles.items()
            },
        }


class SimulatedSecopNode(StateMachineDevice):
    def _initialize_data(self):
        """Initialize the device's attributes."""
        self.modules = {
            "one_of_everything": OneOfEachDtypeModule(),
        }

    def _get_state_handlers(self):
        return {"default": DefaultState()}

    def _get_initial_state(self):
        return "default"

    def _get_transition_handlers(self):
        return OrderedDict([])

    def descriptor(self) -> dict[str, typing.Any]:
        return {
            "equipment_id": __name__,
            "description": "SECoP lewis emulator",
            "modules": {name: module.descriptor() for name, module in self.modules.items()},
        }
