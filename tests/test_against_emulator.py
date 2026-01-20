import asyncio
import math
import os.path
import subprocess
import sys
import typing

import numpy as np
import pytest
from fastcs import FastCS
from fastcs.attributes import AttrR
from fastcs.connections import IPConnectionSettings
from fastcs.logging import LogLevel, configure_logging

from fastcs_secop import SecopController

configure_logging(level=LogLevel.TRACE)


@pytest.fixture(autouse=True, scope="class")
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
            "stream: {bind_address: 127.0.0.1, port: 57677}",
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
        ),
    )

    for _ in range(100):
        try:
            await controller.connect()
            break
        except Exception:
            await asyncio.sleep(0.1)
    else:
        raise RuntimeError("Could not connect to emulator within 10s")

    fastcs = FastCS(
        controller,
        [],
    )

    fastcs_task = asyncio.create_task(fastcs.serve(interactive=False))

    # Wait for FastCS to have run initialise() & created attributes
    max_iters = 100  # 10 seconds
    for _ in range(max_iters):
        if controller.sub_controllers:
            break
        await asyncio.sleep(0.1)
    else:
        raise RuntimeError("No subcontrollers created within 10s of FastCS serve")

    try:
        yield controller
    finally:
        fastcs_task.cancel()
        await fastcs_task


class TestInitialState:
    def test_sub_controllers_created(self, controller):
        assert "one_of_everything" in controller.sub_controllers

    @pytest.mark.parametrize(
        ("param", "expected_initial_value"),
        [
            ("double", 1.2345),
            ("scaled", 42 * 47),
            ("int", 73),
            ("bool", True),
            ("string", "hello"),
        ],
    )
    async def test_attributes_created_for_simple_datatype(
        self, controller, param, expected_initial_value
    ):
        attr: AttrR = typing.cast(
            AttrR, controller.sub_controllers["one_of_everything"].attributes[param]
        )
        await attr.wait_for_value(expected_initial_value, timeout=2)

    async def test_attributes_created_for_enum_datatype(self, controller):
        attr: AttrR = typing.cast(
            AttrR, controller.sub_controllers["one_of_everything"].attributes["enum"]
        )
        await attr.wait_for_predicate(lambda v: v.name == "three", timeout=2)

    @pytest.mark.parametrize(
        ("param", "expected_initial_value"),
        [
            ("blob", np.array([c for c in b"a blob of binary data"], dtype=np.uint8)),
            ("int_array", np.array([1, 1, 2, 3, 5, 8, 13], dtype=np.int32)),
            ("bool_array", np.array([1, 1, 0, 1, 0, 0, 1, 1], dtype=np.uint8)),
            ("double_array", np.array([1.414, 1.618, math.e, math.pi], dtype=np.float64)),
            (
                "tuple",
                np.array(
                    [(1, 5.678, 1, "hiya", 5)],
                    dtype=[
                        ("e0", np.int32),
                        ("e1", np.float64),
                        ("e2", np.uint8),
                        ("e3", "<U512"),
                        ("e4", np.int32),
                    ],
                ),
            ),
            (
                "struct",
                np.array(
                    [(42, math.pi, 1, "chillin'", 1)],
                    dtype=[
                        ("answer", np.int32),
                        ("pi", np.float64),
                        ("on_fire", np.uint8),
                        ("status", "<U512"),
                        ("mode", np.int32),
                    ],
                ),
            ),
        ],
    )
    async def test_attributes_created_for_array_datatype(
        self, controller, param, expected_initial_value
    ):
        attr: AttrR = typing.cast(
            AttrR, controller.sub_controllers["one_of_everything"].attributes[param]
        )
        await attr.wait_for_predicate(
            lambda v: np.array_equal(v, expected_initial_value), timeout=2
        )

    @pytest.mark.parametrize(
        ("command", "expected_attributes"),
        [
            ("command_bool_int", {"args", "result"}),
            ("command_null_int", {"result"}),
            ("command_bool_null", {"args"}),
            ("command_null_null", set()),
        ],
    )
    async def test_command_attributes_created(self, controller, command, expected_attributes):
        cmd_controller = controller.sub_controllers["one_of_everything"].sub_controllers[command]
        assert set(cmd_controller.attributes.keys()) == expected_attributes
