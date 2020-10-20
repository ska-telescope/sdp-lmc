"""SDP Tango device base class module."""

import enum
import logging
import threading

from tango import AttrWriteType, ErrSeverity, Except, EnsureOmniThread
from tango.server import Device, command, attribute

from ska_sdp_config.config import Transaction
from . import release
from .feature_toggle import FeatureToggle

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
            LOG.debug('Setting device state to %s', value.name)
            self.set_state(value)

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
        return thread

    def _event_loop(self):
        """Event loop to update attributes automatically."""
        LOG.info('Starting event loop')
        # Use EnsureOmniThread to make it thread-safe under Tango
        with EnsureOmniThread():
            self._set_attributes()

    def update_attributes(self):
        """Update the device attributes manually."""
        LOG.info('Updating attributes')
        self._set_attributes(loop=False)

    def _set_attributes(self, loop: bool = True) -> None:
        """Set attributes based on configuration.

        if `loop` is `True`, it acts as an event loop to watch for changes to
        the configuration. If `loop` is `False` it makes a single pass.

        :param loop: watch for changes to configuration and loop

        """
        for txn in self._config.txn():
            self._set_from_config(txn)
            if loop:
                # Loop the transaction when the config entries are changed
                txn.loop(wait=True)

    def _set_from_config(self, txn: Transaction) -> None:
        """Subclasses override this to set their state."""
        pass

    @staticmethod
    def _raise_exception(reason, desc, origin, severity=ErrSeverity.ERR):
        """Raise a Tango DevFailed exception.

        :param reason: Reason for the error.
        :param desc: Error description.
        :param origin: Error origin.

        """
        LOG.error('Raising DevFailed exception...')
        LOG.error('Reason: %s', reason)
        LOG.error('Description: %s', desc)
        LOG.error('Origin: %s', origin)
        LOG.error('Severity: %s', severity)
        Except.throw_exception(reason, desc, origin, severity)

    def _raise_command_not_allowed(self, desc, origin):
        """Raise a command-not-allowed exception.

        :param desc: Error description.
        :param origin: Error origin.

        """
        self._raise_exception('API_CommandNotAllowed', desc, origin)

    def _raise_command_failed(self, desc, origin):
        """Raise a command-failed exception.

        :param desc: Error description.
        :param origin: Error origin.

        """
        self._raise_exception('API_CommandFailed', desc, origin)

    def _command_allowed(self, commname, attrname, value, allowed):
        """Check command is allowed when an attribute has its current value.

        If the command is not allowed, it raises a Tango API_CommandNotAllowed
        exception. This generic method is used by other methods to check
        specific attributes.

        :param commname: name of the command
        :param attrname: name of the attribute
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
            message = f'Command {commname} not allowed when {attrname} is ' \
                      f'{value_message}'
            origin = f'{type(self).__name__}.is_{commname}_allowed()'
            self._raise_command_not_allowed(message, origin)

    def _command_allowed_state(self, commname, allowed):
        """Check command is allowed in the current device state.

        :param commname: name of the command
        :param allowed: list of allowed device state values

        """
        self._command_allowed(commname, 'device state', self.get_state(),
                              allowed)
