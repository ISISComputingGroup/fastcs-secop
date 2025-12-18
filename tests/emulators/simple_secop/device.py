import time
import typing
from collections import OrderedDict

from lewis.devices import StateMachineDevice

from .states import DefaultState


class Accessible:
    def __init__(self):
        self.description = ""


class Parameter(Accessible):
    def __init__(self, value):
        super().__init__()
        self.value = value

    def data_report(self):
        return [
            self.value,
            {
                "t": time.time(),
            },
        ]

    def descriptor(self) -> dict[str, typing.Any]:
        return {
            "description": "some_parameter_description",
            "datainfo": {
                "type": "double",
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


class Module:
    def __init__(self):
        self.accessibles = {
            "p1": Parameter(1),
            "p2": Parameter(2),
            "p3": Parameter(3),
        }
        self.description = "foo"

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
            "mod1": Module(),
            "mod2": Module(),
            "mod3": Module(),
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
