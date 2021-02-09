"""Event loop support"""
import logging
import threading
from time import sleep
from typing import Callable, Any, Optional

from tango import EnsureOmniThread
from tango.server import command

from .feature_toggle import FeatureToggle

LOG = logging.getLogger('ska_sdp_lmc')
FEATURE_EVENT_LOOP = FeatureToggle('event_loop', True)

# *** This needs some cleanup to remove any useless stuff.


def new_event_loop(device):
    """
    Factory function to create an "event loop".

    If the event loop feature is on, this returns a thread, otherwise it returns an
    object with methods that operate synchronously.

    :param device: SDP device
    :return "event loop"
    """
    return _RealThread(device) if FEATURE_EVENT_LOOP.is_active() else _FakeThread(device)


def _add_command(device):
    cmd = command(f=device.update_attributes)
    device.add_command(cmd, True)


class _FakeCondition:
    def __enter__(self):
        """Does nothing."""
    def __exit__(self):
        """Does nothing."""


class _FakeThread:
    def __init__(self, device):
        _add_command(device)
        self.condition = _FakeCondition()

    def start(self):
        """Does nothing."""

    def notify(self):
        """Does nothing."""

    def join(self):
        """Does nothing."""

    def wait(self):
        """Does nothing."""

    def acquire(self):
        """Does nothing."""

    def release(self):
        """Does nothing."""

    @staticmethod
    def do(f: Callable, name: str, *args, **kwargs) -> Any:
        return f(*args, **kwargs)


class _RealThread(threading.Thread):
    def __init__(self, device):
        super().__init__(target=self._event_loop, name='EventLoop', daemon=True)
        self.device = device
        _add_command(device)
        self.condition = threading.Condition()

    def _event_loop(self):
        """Event loop to update attributes automatically."""
        LOG.info('Starting event loop')
        # Use EnsureOmniThread to make it thread-safe under Tango
        with EnsureOmniThread():
            self.device.set_attributes()

    def wait(self) -> None:
        LOG.info('Wait called')
        with self.condition:
            LOG.info('Waiting')
            self.condition.wait()
            LOG.info('Done waiting')

    def acquire(self):
        self.condition.acquire()

    def release(self):
        self.condition.release()

    def notify(self) -> None:
        logging.info('Notify waiting threads')
        with self.condition:
            self.condition.notify_all()
        logging.info('Notified waiting threads')

    def join(self, timeout: Optional[float] = None) -> None:
        LOG.info('Waiting for event thread to terminate')
        super().join(timeout)
        LOG.info('Event thread stopped')

    def do(self, f: Callable, name: str, *args, **kwargs) -> Any:
        LOG.info('Call %s', name)
        with self.condition:
            LOG.info('Execute %s', name)
            ret = f(*args, **kwargs)
            LOG.info('Waiting for update')
            sleep(2)
            #self.condition.wait()
        LOG.info('Update received')
        return ret



