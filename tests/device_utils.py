"""Utilities for device tests."""

import time
from typing import Callable

import tango

from ska_sdp_lmc import tango_logging, base
from . import test_logging

LOG_LIST = test_logging.ListHandler()
LOG = tango_logging.get_logger()
SLEEP = 0.05
TIMEOUT = 5.0


def init_device(devices, name: str):
    """Initialise a device."""
    device = devices.get_device(name)

    # Configure logging to be captured
    LOG_LIST.clear()
    tango_logging.configure(
        device, device_name=name, handlers=[LOG_LIST], level=tango.LogLevel.LOG_DEBUG
    )

    # Update the device attributes if the event loop is not running
    update_attributes(device)

    # Clear remembered command exception
    device.exception = None

    return device


def update_attributes(device):
    """Update attribute if event loop is not running."""
    if not base.FEATURE_EVENT_LOOP.is_active():
        device.update_attributes()


def wait_for(
    predicate: Callable, timeout: float = TIMEOUT, sleep: float = SLEEP
) -> None:
    """Wait for predicate to be true."""
    elapsed = 0.0
    while not predicate() and elapsed < timeout:
        time.sleep(sleep)
        elapsed += sleep
    if elapsed >= timeout:
        LOG.warning("Timeout occurred while waiting")


def wait_for_state(device, state):
    """Wait for device state to reach the required value."""
    wait_for(lambda: device.state() == state)
