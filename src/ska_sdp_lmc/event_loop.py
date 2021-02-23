"""Event loop support"""
import contextlib
import threading
from typing import Callable, Any, Optional

from tango import EnsureOmniThread
from tango.server import command

from . import tango_logging
from .feature_toggle import FeatureToggle

LOG = tango_logging.get_logger()
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


def _add_commands(device):
    """Add commands that the tests can use."""
    for f in (device.update_attributes, device.wait_for_event, device.flush_event_queue,
              device.acquire, device.release, device.stop_event_loop):
        cmd = command(f=f)
        device.add_command(cmd, True)


class _FakeThread:
    def __init__(self, device):
        _add_commands(device)
        self.condition = contextlib.nullcontext()

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
        _add_commands(device)
        self.condition = threading.Condition()

    def _event_loop(self):
        """Event loop to update attributes automatically."""
        LOG.info('Starting event loop, name=%s', self.name)
        # Use EnsureOmniThread to make it thread-safe under Tango
        with EnsureOmniThread():
            self.device.set_attributes()

    def wait(self) -> None:
        with self.condition:
            LOG.info('Waiting for event')
            self.condition.wait()
            LOG.info('Done waiting')

    def acquire(self):
        self.condition.acquire()

    def release(self):
        self.condition.release()

    def notify(self) -> None:
        LOG.debug('Notify waiting threads')
        with self.condition:
            self.condition.notify_all()
        LOG.debug('Notified waiting threads')

    def join(self, timeout: Optional[float] = None) -> None:
        LOG.info('Waiting for event thread to terminate')
        super().join(timeout)
        LOG.info('Event thread stopped')

    def do(self, f: Callable, name: str, *args, **kwargs) -> Any:
        # Execute command with a condition lock and wait for
        # notification from the event thread.
        LOG.info('Call %s', name)
        with self.condition:
            ret = f(*args, **kwargs)
            LOG.info('Waiting for update')
            self.condition.wait()
        LOG.info('Update received')
        return ret



