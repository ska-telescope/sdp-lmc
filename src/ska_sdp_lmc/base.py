"""SDP Tango device base class module."""

import enum
import logging
import traceback

from tango import AttrWriteType
from tango.server import Device, attribute

from ska_sdp_config.config import Transaction
from . import release
from .event_loop import new_event_loop
from .exceptions import raise_command_not_allowed

LOG = logging.getLogger('ska_sdp_lmc')


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
        self._event_loop = new_event_loop(self)
        self._deleting = False
        self._watcher = None

    def delete_device(self):
        """Device destructor."""
        LOG.info('Deleting %s device: %s', self._get_device_name().lower(),
                 self.get_name())
        self._deleting = True
        if self._watcher is not None:
            LOG.info('trigger watcher loop')
            self._watcher.trigger()
            self._watcher = None
        self._event_loop.join()

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
        if value is not None and self.get_state() != value:
            LOG.info('Setting device state to %s', value.name)
            self.set_state(value)
            self.push_change_event('State', self.get_state())

    @classmethod
    def _get_device_name(cls):
        # This gets the class name minus SDP e.g. Master
        return cls.__name__.split('SDP')[1]

    def update_attributes(self):
        """Update the device attributes manually."""
        LOG.info('Updating attributes')
        self.set_attributes(loop=False)

    def _do_transaction(self, txn_wrapper):
        for txn in txn_wrapper.txn():
            LOG.info('txn is %s', txn)
            with self._event_loop.condition:
                LOG.info('call set from config')
                self._set_from_config(txn)
                self._event_loop.notify()

    def set_attributes(self, loop: bool = True) -> None:
        """Set attributes based on configuration.

        if `loop` is `True`, it acts as an event loop to watch for changes to
        the configuration. If `loop` is `False` it makes a single pass.

        :param loop: watch for changes to configuration and loop

        """
        LOG.info('deleting: %s loop: %s', self._deleting, loop)
        if loop:
            try:
                for watcher in self._config.watcher():
                    LOG.info('watcher is %s', type(watcher))
                    if self._deleting:
                        break
                    self._watcher = watcher
                    self._do_transaction(watcher)
            finally:
                self._watcher = None
            LOG.info('Exit watcher loop')
        else:
            LOG.info('set attributes without watch')
            self._do_transaction(self._config)
        LOG.info('Exit set attributes')

    def _set_from_config(self, txn: Transaction) -> None:
        """Subclasses override this to set their state."""

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
