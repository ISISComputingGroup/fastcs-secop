from unittest.mock import AsyncMock, patch

import pytest
from fastcs.connections import IPConnectionSettings

from fastcs_secop.controllers import (
    SecopController,
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
