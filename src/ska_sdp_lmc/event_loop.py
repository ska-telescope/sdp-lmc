"""Event loop support"""
import logging
import threading
from typing import Callable, Any

from tango import EnsureOmniThread
from tango.server import command

from .feature_toggle import FeatureToggle

LOG = logging.getLogger('ska_sdp_lmc')
FEATURE_EVENT_LOOP = FeatureToggle('event_loop', True)


def new_event_loop(device):
    """
    Factory function to create an "event loop".

    If the event loop feature is on, this returns a thread, otherwise it returns an
    object with methods that operate synchronously.

    :param device: SDP device
    :return "event loop"
    """
    return _RealThread(device) if FEATURE_EVENT_LOOP.is_active() else _FakeThread(device)


class _FakeThread:
    def __init__(self, device):
        cmd = command(f=device.update_attributes)
        device.add_command(cmd, True)

    def start(self):
        """Does nothing."""

    def notify(self):
        """Does nothing."""

    def join(self):
        """Does nothing."""

    @staticmethod
    def do(f: Callable, *args, **kwargs) -> Any:
        return f(*args, **kwargs)


class _RealThread(threading.Thread):
    def __init__(self, device):
        super().__init__(target=self._event_loop, name='EventLoop', daemon=True)
        self.device = device
        self.condition = threading.Condition()

    def _event_loop(self):
        """Event loop to update attributes automatically."""
        LOG.info('Starting event loop')
        # Use EnsureOmniThread to make it thread-safe under Tango
        with EnsureOmniThread():
            self.device.set_attributes()

    def notify(self):
        with self.condition:
            self.condition.notifyAll()

    def do(self, f: Callable, *args, **kwargs) -> Any:
        with self.condition:
            ret = f(*args, **kwargs)
            self.condition.wait()
        return ret



