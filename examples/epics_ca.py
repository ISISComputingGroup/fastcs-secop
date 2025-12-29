"""Example CA IOC using :py:obj:`fastcs_secop`."""

import asyncio
import logging
import socket

from fastcs.connections import IPConnectionSettings
from fastcs.launch import FastCS
from fastcs.logging import LogLevel, configure_logging

from fastcs_secop import SecopQuirks
from fastcs_secop.controllers import SecopController

if __name__ == "__main__":
    from fastcs.transports import EpicsIOCOptions
    from fastcs.transports.epics.ca import EpicsCATransport

    configure_logging(level=LogLevel.DEBUG)
    logging.basicConfig(level=LogLevel.DEBUG)

    asyncio.get_event_loop().slow_callback_duration = 1000

    epics_options = EpicsIOCOptions(pv_prefix=f"TE:{socket.gethostname().upper()}:SECOP")
    epics_ca = EpicsCATransport(epicsca=epics_options)

    quirks = SecopQuirks(raw_tuple=True, raw_struct=True, max_description_length=40)

    LEWIS = 57677
    DOCKER_GASFLOW = 10801

    controller = SecopController(
        settings=IPConnectionSettings(ip="127.0.0.1", port=LEWIS),
        quirks=quirks,
    )

    fastcs = FastCS(
        controller,
        [epics_ca],
    )
    fastcs.run(interactive=True)
