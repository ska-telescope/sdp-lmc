"""Utilities for device tests."""
from typing import Callable

import tango

from . import test_logging
from ska_sdp_lmc import tango_logging

LOG_LIST = test_logging.ListHandler()
LOG = tango_logging.get_logger()


def init_device(devices, name: str, wipe_config_db: Callable):
    device = devices.get_device(name)

    # Configure logging to be captured
    LOG_LIST.clear()
    tango_logging.configure(device, device_name=name, handlers=[LOG_LIST],
                            level=tango.LogLevel.LOG_DEBUG)

    # Wipe the config DB
    wipe_config_db()

    # Initialise the device
    device.Init()

    # Update the device attributes
    device.update_attributes()

    return device
