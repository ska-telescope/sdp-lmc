"""Utilities for device tests."""
from typing import Callable

import tango

from . import test_logging
from ska_sdp_lmc import event_loop, tango_logging

LOG_LIST = test_logging.ListHandler()
LOG = tango_logging.get_logger()


def check_configured(device) -> bool:
    # Check if device is fully configured (it's not from
    # MultiDeviceTestContext initialisation).
    is_configured = hasattr(device, 'stop_event_loop')
    if is_configured:
        LOG.info('stop event loop')
        device.stop_event_loop()
    else:
        LOG.info('device not fully configured')
    return is_configured


def update_attributes(device, wait=True) -> None:
    if event_loop.FEATURE_EVENT_LOOP.is_active():
        if wait:
            device.wait_for_event()
    else:
        device.update_attributes()
    device.flush_update_queue()

def init_device(devices, name: str, wipe_config_db: Callable):
    device = devices.get_device(name)

    # Configure logging to be captured
    LOG_LIST.clear()
    tango_logging.configure(device, device_name=name, handlers=[LOG_LIST],
                            level=tango.LogLevel.LOG_DEBUG)
    check_configured(device)

    # Wipe the config DB
    wipe_config_db()

    # Initialise the device
    device.Init()

    # Update the device attributes
    update_attributes(device)

    return device
