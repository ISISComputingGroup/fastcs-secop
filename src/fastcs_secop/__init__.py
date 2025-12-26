"""SECoP support using FastCS."""

import logging
from logging import getLogger

from fastcs.connections import IPConnectionSettings
from fastcs.launch import FastCS
from fastcs.logging import LogLevel, configure_logging
from fastcs.transports import EpicsIOCOptions, EpicsPVATransport
from fastcs.transports.epics.ca import EpicsCATransport

from fastcs_secop._util import SecopError
from fastcs_secop.controllers import SecopController

logger = getLogger(__name__)

__all__ = ["SecopError"]


if __name__ == "__main__":  # pragma: no cover
    configure_logging(level=LogLevel.DEBUG)

    logging.basicConfig(level=LogLevel.DEBUG)

    epics_options = EpicsIOCOptions(pv_prefix="TE:NDW2922:SECOP")
    epics_ca = EpicsCATransport(epicsca=epics_options)
    epics_pva = EpicsPVATransport(epicspva=epics_options)

    fastcs = FastCS(
        SecopController(settings=IPConnectionSettings(ip="127.0.0.1", port=57677)),
        [epics_pva],
    )
    fastcs.run(interactive=False)
