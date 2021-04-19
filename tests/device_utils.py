"""Utilities for device tests."""
import time
from typing import Callable, Sequence, List

from tango import EventType, EventData, LogLevel, DataReadyEventData

from . import test_logging
from ska_sdp_lmc import tango_logging, base

LOG_LIST = test_logging.ListHandler()
LOG = tango_logging.get_logger()


def wait_for(predicate: Callable, timeout: float = 5.0, sleep: float = 0.1) -> None:
    """Wait for predicate to be true."""
    elapsed = 0.0
    while not predicate() and elapsed < timeout:
        time.sleep(sleep)
        elapsed += sleep
    if elapsed >= timeout:
        LOG.warning("Timeout occurred while waiting")


class Monitor:
    """
    Monitor an attribute of a device.

    Could be promoted from tests to utilities api?
    """
    _instances = {}

    def __init__(self, device, attribute: str):
        self.device = device
        self.attribute = attribute
        self.value = ""
        self.changed = False
        # self.event_id = None
        key = self.to_key(device, attribute)
        Monitor._instances[key] = self
        LOG.info("Subscribing to change events on %s", key)
        self.change_id = device.subscribe_event(attribute, EventType.CHANGE_EVENT,
                                                self._change)
        if self.attribute != "State":
            # I can't find a way to do this for state.
            self.ready_id = device.subscribe_event(attribute, EventType.DATA_READY_EVENT,
                                                   self._ready)
        else:
            self.ready_id = None

    @staticmethod
    def to_key(device, attribute: str) -> str:
        return ":".join((device.dev_name(), attribute))

    def get_key(self):
        return Monitor.to_key(self.device, self.attribute)

    @staticmethod
    def get_instance(device, attribute: str) -> "Monitor":
        return Monitor._instances[Monitor.to_key(device, attribute)]

    @staticmethod
    def get_state_instance(device) -> "Monitor":
        return Monitor.get_instance(device, 'State')

    def _event(self, event_type: str, ed):
        s = ed.attr_name.rfind('/') + 1
        e = ed.attr_name.rfind('#')
        LOG.info("%s event for %s: %s -> %s", event_type, ed.device,
                 ed.attr_name[s:e], self.value)

    def _change(self, ed: EventData):
        self.value = str(ed.attr_value.value)
        self.changed = True
        self._event("Change", ed)

    def _ready(self, ed: DataReadyEventData):
        self.changed = True
        self._event("Ready", ed)

    def _check_for_change(self):
        changed = self.changed
        if changed:
            # Reset flag.
            self.changed = False
        return changed

    def wait_for(self, predicate: Callable, timeout: float = 5.0, sleep: float = 0.1) -> str:
        wait_for(predicate, timeout, sleep)
        return self.value

    def wait_for_value(self, value: str, timeout: float = 5.0, sleep: float = 0.1) -> str:
        def predicate():
            LOG.debug("Test if %s is %s", self.value, value)
            return self.value == value

        value = self.wait_for(predicate, timeout, sleep)
        self._check_for_change()
        return value

    def wait_for_change(self, timeout: float = 5.0, sleep: float = 0.1) -> str:
        return self.wait_for(self._check_for_change, timeout, sleep)

    def close(self):
        self.device.unsubscribe_event(self.change_id)
        if self.ready_id is not None:
            self.device.unsubscribe_event(self.ready_id)
        Monitor._instances.pop(self.get_key())

    @staticmethod
    def close_all():
        for instance in Monitor._instances.copy().values():
            instance.close()

    def __repr__(self):
        return self.get_key()


def feature_check(device):
    if not base.FEATURE_EVENT_LOOP.is_active():
        device.update_attributes()


def wait_for_state_change(device) -> None:
    feature_check(device)
    Monitor.get_state_instance(device).wait_for_change()


def wait_for_state(device, state: str) -> None:
    feature_check(device)
    Monitor.get_state_instance(device).wait_for_value(state)


def wait_for_multiple(device, attributes: Sequence[str],
                      predicate: Callable[[Sequence[Monitor]], bool]) -> None:
    feature_check(device)
    monitors = [Monitor.get_instance(device, attr) for attr in attributes]
    wait_for(lambda: predicate(monitors))
    for mon in monitors:
        mon.changed = False


def wait_for_changes(device, attributes: Sequence[str]) -> None:
    wait_for_multiple(device, attributes,
                      lambda monitors: all([mon.changed for mon in monitors]))


def wait_for_values(device, attributes: List[str], values: List[str]) -> None:
    wait_for_multiple(device, attributes, lambda monitors:
                      all([monitors[i].value == values[i] for i in range(len(monitors))]))


def init_device(devices, name: str, wipe_config_db: Callable):
    """Initialise a device."""
    device = devices.get_device(name)

    # Configure logging to be captured
    LOG_LIST.clear()
    tango_logging.configure(device, device_name=name, handlers=[LOG_LIST],
                            level=LogLevel.LOG_DEBUG)

    # Wipe the config DB
    wipe_config_db()

    # Initialise the device
    device.Init()

    # Update the device attributes
    device.update_attributes()

    return device
