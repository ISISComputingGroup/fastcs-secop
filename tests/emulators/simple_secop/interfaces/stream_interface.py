import json
import typing

from lewis.adapters.stream import StreamInterface
from lewis.core.logging import has_log
from lewis.utils.command_builder import CmdBuilder


@has_log
class SimpleSecopStreamInterface(StreamInterface):
    commands = {
        # ID
        CmdBuilder("idn").escape("*IDN?").optional("\r").eos().build(),
        CmdBuilder("describe").escape("describe").optional("\r").eos().build(),
        CmdBuilder("change")
        .escape("change ")
        .any_except(":")
        .escape(":")
        .any_except(" ")
        .escape(" ")
        .arg(".*", argument_mapping=json.loads)
        .optional("\r")
        .eos()
        .build(),
        CmdBuilder("read")
        .escape("read ")
        .any_except(":")
        .escape(":")
        .any_except("\r")
        .optional("\r")
        .eos()
        .build(),
    }

    in_terminator = "\n"
    out_terminator = "\n"

    def handle_error(self, request, error):
        err_string = "command was: {}, error was: {}: {}\n".format(
            request, error.__class__.__name__, error
        )
        print(err_string)
        self.log.error(err_string)
        return err_string

    def idn(self):
        return "ISSE&SINE2020,SECoP,V0000.00.00,lewis_emulator"

    def describe(self):
        return f"describing . {json.dumps(self._device.descriptor())}"

    def change(self, module: str, accessible: str, value: typing.Any):
        self._device.modules[module].accessibles[accessible].change(value)
        data_report = self._device.modules[module].accessibles[accessible].data_report()
        return f"changed {module}:{accessible} {json.dumps(data_report)}"

    def read(self, module: str, accessible: str):
        data_report = self._device.modules[module].accessibles[accessible].data_report()
        return f"reply {module}:{accessible} {json.dumps(data_report)}"
