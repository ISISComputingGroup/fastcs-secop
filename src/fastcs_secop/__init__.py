"""SECoP support using FastCS."""

import asyncio
import logging
from collections import defaultdict
from logging import getLogger

from fastcs.connections import IPConnectionSettings
from fastcs.launch import FastCS
from fastcs.logging import LogLevel, configure_logging
from fastcs.transports import EpicsIOCOptions, EpicsPVATransport
from fastcs.transports.epics.ca import EpicsCATransport

from fastcs_secop._util import SecopError, SecopQuirks
from fastcs_secop.controllers import SecopController

logger = getLogger(__name__)

__all__ = ["SecopError", "SecopQuirks"]


if __name__ == "__main__":  # pragma: no cover
    configure_logging(level=LogLevel.DEBUG)

    logging.basicConfig(level=LogLevel.DEBUG)

    asyncio.get_event_loop().slow_callback_duration = 1000

    epics_options = EpicsIOCOptions(pv_prefix="TE:NDW2922:SECOP")
    epics_ca = EpicsCATransport(epicsca=epics_options)
    epics_pva = EpicsPVATransport(epicspva=epics_options)

    quirks = defaultdict(
        lambda: SecopQuirks(raw_tuple=False, raw_struct=False, max_description_length=40)
    )
    quirks["valve_controller._domains_to_extract"] = SecopQuirks(raw_array=True)
    quirks["valve_controller._terminal_values"] = SecopQuirks(raw_struct=True)

    LEWIS = 57677
    DOCKER_GASFLOW = 10801

    fastcs = FastCS(
        SecopController(
            settings=IPConnectionSettings(ip="127.0.0.1", port=LEWIS),
            quirks=quirks,
        ),
        [epics_pva],
    )
    fastcs.run(interactive=True)
