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
    assert "mod1" in controller.sub_controllers
    assert "mod2" in controller.sub_controllers
    assert "mod3" in controller.sub_controllers


async def test_attributes_created(controller):
    for mod in ["mod1", "mod2", "mod3"]:
        assert "p1" in controller.sub_controllers[mod].attributes
        assert "p2" in controller.sub_controllers[mod].attributes
        assert "p3" in controller.sub_controllers[mod].attributes
