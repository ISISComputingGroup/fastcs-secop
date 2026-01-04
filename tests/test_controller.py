from unittest.mock import AsyncMock, patch

import orjson
import pytest
from fastcs.connections import IPConnectionSettings

from fastcs_secop import (
    SecopCommandController,
    SecopController,
    SecopError,
    SecopModuleController,
    SecopQuirks,
)


@pytest.fixture
def controller():
    controller = SecopController(
        settings=IPConnectionSettings(
            ip="127.0.0.1",
            port=65535,
        )
    )
    return controller


async def test_ping_happy_path(controller):
    with patch.object(controller._connection, "send_query", AsyncMock(return_value="pong")):
        controller.connect = AsyncMock()
        await controller.ping()
        controller.connect.assert_not_awaited()


async def test_ping_raises_disconnected_error(controller):
    with patch.object(controller._connection, "send_query", AsyncMock(side_effect=ConnectionError)):
        controller.connect = AsyncMock()
        await controller.ping()
        controller.connect.assert_awaited()


async def test_ping_raises_disconnected_error_and_reconnect_fails(controller):
    with patch.object(controller._connection, "send_query", AsyncMock(side_effect=ConnectionError)):
        controller.connect = AsyncMock(side_effect=ConnectionError)
        await controller.ping()
        controller.connect.assert_awaited()


async def test_ping_raises_disconnected_error_and_reconnect_works(controller):
    with patch.object(
        controller._connection, "send_query", AsyncMock(side_effect=[ConnectionError, "I'm alive"])
    ):
        controller.connect = AsyncMock()
        await controller.ping()
        controller.connect.assert_awaited()


async def test_check_idn():
    controller = SecopController(settings=IPConnectionSettings("127.0.0.1", 0))
    controller._connection = AsyncMock()

    controller._connection.send_query.return_value = "ISSE&SINE2020,SECoP,foo,bar"
    await controller.check_idn()

    controller._connection.send_query.return_value = "ISSE,SECoP,foo,bar"
    await controller.check_idn()

    controller._connection.send_query.return_value = "blah,blah,blah,blah"
    with pytest.raises(SecopError):
        await controller.check_idn()

    controller._connection.send_query.return_value = "ISSE,not_secop,blah,blah"
    with pytest.raises(SecopError):
        await controller.check_idn()

    controller._connection.send_query.return_value = "a_random_device"
    with pytest.raises(SecopError):
        await controller.check_idn()


async def test_create_modules():
    controller = SecopController(
        settings=IPConnectionSettings("127.0.0.1", 0),
        quirks=SecopQuirks(skip_modules="a_skipped_module"),
    )
    controller._connection = AsyncMock()
    controller._connection.send_query.return_value = (
        "describing . "
        + orjson.dumps(
            {
                "description": "some description",
                "equipment_id": "some equipment id",
                "modules": {
                    "a_cool_module": {"accessibles": {}},
                    "another_cool_module": {"accessibles": {}},
                    "a_skipped_module": {"accessibles": {}},
                },
            }
        ).decode()
        + "\n"
    )

    await controller._create_modules()
    assert "a_cool_module" in controller.sub_controllers
    assert "another_cool_module" in controller.sub_controllers
    assert "a_skipped_module" not in controller.sub_controllers


async def test_create_modules_bad_description():
    controller = SecopController(
        settings=IPConnectionSettings("127.0.0.1", 0),
        quirks=SecopQuirks(skip_modules="a_skipped_module"),
    )
    controller._connection = AsyncMock()
    controller._connection.send_query.return_value = "a huge pile of nonsense\n"

    with pytest.raises(SecopError):
        await controller._create_modules()


async def test_secop_module_controller_initialise():
    connection = AsyncMock()
    controller = SecopModuleController(
        connection=connection,
        module_name="some_module",
        module={
            "accessibles": {
                "normal_accessible": {"datainfo": {"type": "int"}},
                "skipped_accessible": {"datainfo": {"type": "int"}},
                "raw_accessible": {"datainfo": {"type": "int"}},
            }
        },
        quirks=SecopQuirks(
            skip_accessibles=[("some_module", "skipped_accessible")],
            raw_accessibles=[("some_module", "raw_accessible")],
        ),
    )

    await controller.initialise()

    assert controller.attributes["normal_accessible"].dtype is int
    assert controller.attributes["raw_accessible"].dtype is str
    assert "skipped_accessible" not in controller.attributes


async def test_command_controller_execute_invalid_response():
    connection = AsyncMock()
    controller = SecopCommandController(
        connection=connection,
        command_name="some_command",
        module_name="some_module",
        datainfo={},
        quirks=SecopQuirks(),
    )
    await controller.initialise()

    connection.send_query.return_value = "blah blah blah this isn't a valid response\n"
    await controller.execute()  # No exception thrown


async def test_command_controller_execute_fails():
    connection = AsyncMock()
    controller = SecopCommandController(
        connection=connection,
        command_name="some_command",
        module_name="some_module",
        datainfo={},
        quirks=SecopQuirks(),
    )
    await controller.initialise()

    connection.send_query.side_effect = Exception
    await controller.execute()  # No exception thrown


async def test_command_controller_execute_no_args_no_return():
    connection = AsyncMock()
    controller = SecopCommandController(
        connection=connection,
        command_name="some_command",
        module_name="some_module",
        datainfo={},
        quirks=SecopQuirks(),
    )
    await controller.initialise()

    connection.send_query.return_value = "done some_module:some_command\n"
    await controller.execute()


async def test_command_controller_execute():
    connection = AsyncMock()
    controller = SecopCommandController(
        connection=connection,
        command_name="some_command",
        module_name="some_module",
        datainfo={"argument": {"type": "int"}, "result": {"type": "int"}},
        quirks=SecopQuirks(),
    )
    await controller.initialise()
    await controller.args.update(13)

    connection.send_query.return_value = 'done some_module:some_command [42, {"t": 123}]\n'
    await controller.execute()

    connection.send_query.assert_awaited_once_with("do some_module:some_command 13\n")
    assert controller.result.get() == 42


async def test_command_controller_execute_raw_args_and_result():
    connection = AsyncMock()
    controller = SecopCommandController(
        connection=connection,
        command_name="some_command",
        module_name="some_module",
        datainfo={"argument": {"type": "tuple"}, "result": {"type": "tuple"}},
        quirks=SecopQuirks(raw_tuple=True),
    )
    await controller.initialise()
    await controller.args.update("[13]")

    connection.send_query.return_value = 'done some_module:some_command [[42], {"t": 123}]\n'
    await controller.execute()

    connection.send_query.assert_awaited_once_with("do some_module:some_command [13]\n")
    assert controller.result.get() == "[42]"
