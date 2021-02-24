"""SDP Tango device base class module."""

import enum
import logging
import threading
from typing import Callable

from tango import AttrWriteType, AutoTangoMonitor, EnsureOmniThread
from tango.server import Device, command, attribute

from ska_sdp_config.config import Transaction
from . import release
from .feature_toggle import FeatureToggle
from .exceptions import raise_command_not_allowed

LOG = logging.getLogger('ska_sdp_lmc')
FEATURE_EVENT_LOOP = FeatureToggle('event_loop', True)


class SDPDevice(Device):
    """SDP Tango device base class."""

    # pylint: disable=attribute-defined-outside-init

    # ----------
    # Attributes
    # ----------

    version = attribute(
        label='Version',
        dtype=str,
        access=AttrWriteType.READ,
        doc='The version of the device'
    )

    # ---------------
    # General methods
    # ---------------

    def init_device(self):
        """Initialise the device."""
        super().init_device()

        # Enable change events on attributes
        self.set_change_event('State', True)

        # Initialise private values of attributes
        self._version = release.VERSION


    def delete_device(self):
        """Device destructor."""
        LOG.info('Deleting %s device: %s', self._get_device_name().lower(),
                 self.get_name())

    def always_executed_hook(self):
        """Run for on each call."""

    # -----------------
    # Attribute methods
    # -----------------

    def read_version(self):
        """Return server version."""
        return self._version

    # ---------------
    # Private methods
    # ---------------

    def _set_state(self, value):
        """Set device state."""
        if self.get_state() != value:
            LOG.info('Setting device state to %s', value.name)
            self.set_state(value)
            self.push_change_event('State', self.get_state())

    @classmethod
    def _get_device_name(cls):
        # This gets the class name minus SDP e.g. Master
        return cls.__name__.split('SDP')[1]

    # ------------------
    # Event loop methods
    # ------------------

    def _start_event_loop(self):
        """Start event loop."""

        if FEATURE_EVENT_LOOP.is_active():
            # The event loop should only be started once.
            if hasattr(self, '_event_thread'):
                LOG.info('Event loop already started')
                return
            # Start event loop in thread
            thread = threading.Thread(
                target=self._event_loop, name='EventLoop', daemon=True
            )
            thread.start()
        else:
            # Add command to manually update attributes
            thread = None
            cmd = command(f=self.update_attributes)
            self.add_command(cmd, True)

        self._event_thread = thread

    def _event_loop(self):
        """Event loop to update attributes automatically."""
        LOG.info('Starting event loop')
        # Use EnsureOmniThread to make it thread-safe under Tango
        with EnsureOmniThread():
            for watcher in self._config.watcher():
                # Get the Tango monitor lock
                with AutoTangoMonitor(self):
                    for txn in watcher.txn():
                        self._set_attr_from_config(txn)

    def update_attributes(self):
        """Update the device attributes manually."""
        LOG.info('Updating attributes')
        for txn in self._config.txn():
            self._set_attr_from_config(txn)

    def _set_attr_from_config(self, txn: Transaction) -> None:
        """
        Set attributes from configuration.

        This is called from the event loop. Subclasses override this to set
        their attributes.

        :param txn: configuration transaction

        """

    def _update_attr_until_condition(self, condition: Callable):
        """
        Update attributes until condition is satisfied.

        :param condition: condition to exit update loop

        """
        for watcher in self._config.watcher():
            for txn in watcher.txn():
                self._set_attr_from_config(txn)
            if condition():
                break

    def _update_attr_until_state(self, values):
        """
        Update attributes until device state reaches one of the values.

        :param values: list of state values

        """
        self._update_attr_until_condition(lambda: self.get_state() in values)

    # -----------------------
    # Command allowed methods
    # -----------------------

    def _command_allowed(self, command_name, attribute_name, value, allowed):
        """Check command is allowed when an attribute has its current value.

        If the command is not allowed, it raises a Tango API_CommandNotAllowed
        exception. This generic method is used by other methods to check
        specific attributes.

        :param command_name: name of the command
        :param attribute_name: name of the attribute
        :param value: current attribute value
        :param allowed: list of allowed attribute values

        """
        if value not in allowed:
            if isinstance(value, enum.IntEnum):
                # Get name from IntEnum (otherwise it would be rendered as its
                # integer value in the message)
                value_message = value.name
            else:
                value_message = value
            message = f'Command {command_name} not allowed when ' \
                      f'{attribute_name} is {value_message}'
            origin = f'{type(self).__name__}.is_{command_name}_allowed()'
            raise_command_not_allowed(message, origin)

    def _command_allowed_state(self, command_name, allowed):
        """Check command is allowed in the current device state.

        :param command_name: name of the command
        :param allowed: list of allowed device state values

        """
        self._command_allowed(command_name, 'device state', self.get_state(),
                              allowed)
