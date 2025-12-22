import os.path
import subprocess
import sys

import pytest
from fastcs.connections import IPConnectionSettings

from fastcs_secop import SecopController


@pytest.fixture(scope="session", autouse=True)
def emulator():
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "lewis",
            "-k",
            "emulators",
            "simple_secop",
            "-p",
            "stream: {bind_address: localhost, port: 57677}",
        ],
        cwd=os.path.dirname(__file__),
    )
    try:
        yield
    finally:
        proc.kill()


@pytest.fixture
async def controller():
    controller = SecopController(
        settings=IPConnectionSettings(
            ip="127.0.0.1",
            port=57677,
        )
    )

    await controller.connect()
    await controller.initialise()
    return controller


async def test_sub_controllers_created(controller):
    assert "one_of_everything" in controller.sub_controllers


@pytest.mark.parametrize(
    "param",
    [
        "double",
        "scaled",
        "int",
        "bool",
        "enum",
        "string",
        "blob",
        "int_array",
        "bool_array",
        "double_array",
    ],
)
async def test_attributes_created(controller, param):
    assert param in controller.sub_controllers["one_of_everything"].attributes
