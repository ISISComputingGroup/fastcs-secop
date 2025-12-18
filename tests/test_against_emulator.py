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


async def test_sub_controllers_created():
    controller = SecopController(
        settings=IPConnectionSettings(
            ip="127.0.0.1",
            port=57677,
        )
    )

    await controller.connect()
    await controller.initialise()

    assert "mod1" in controller.sub_controllers
    assert "mod2" in controller.sub_controllers
    assert "mod3" in controller.sub_controllers
