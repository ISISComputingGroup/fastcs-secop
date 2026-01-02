"""Example PVA IOC using :py:obj:`fastcs_secop`."""

import argparse
import asyncio
import logging
import socket

from fastcs.connections import IPConnectionSettings
from fastcs.launch import FastCS
from fastcs.logging import LogLevel, configure_logging

from fastcs_secop import SecopController, SecopQuirks

if __name__ == "__main__":
    from fastcs.transports import EpicsIOCOptions
    from fastcs.transports.epics.pva import EpicsPVATransport

    parser = argparse.ArgumentParser(description="Demo PVA ioc")
    parser.add_argument("-i", "--ip", type=str, default="127.0.0.1", help="IP to connect to")
    parser.add_argument("-p", "--port", type=int, help="Port to connect to")
    args = parser.parse_args()

    configure_logging(level=LogLevel.DEBUG)
    logging.basicConfig(level=LogLevel.DEBUG)

    asyncio.get_event_loop().slow_callback_duration = 1000

    epics_options = EpicsIOCOptions(pv_prefix=f"TE:{socket.gethostname().upper()}:SECOP")
    epics_pva = EpicsPVATransport(epicspva=epics_options)

    quirks = SecopQuirks(
        raw_accessibles=[
            ("valve_controller", "_domains_to_extract"),
            ("valve_controller", "_terminal_values"),
        ],
    )

    controller = SecopController(
        settings=IPConnectionSettings(ip=args.ip, port=args.port),
        quirks=quirks,
    )

    fastcs = FastCS(
        controller,
        [epics_pva],
    )
    fastcs.run(interactive=True)
