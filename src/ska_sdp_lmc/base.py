"""SDP Tango device base class module."""

import enum
import threading
from typing import Callable

from tango import AttrWriteType, AutoTangoMonitor, EnsureOmniThread
from tango.server import Device, command, attribute

from ska_sdp_config.config import Transaction
from . import release
from .feature_toggle import FeatureToggle
from .exceptions import raise_command_not_allowed
from .tango_logging import get_logger

LOG = get_logger()
FEATURE_EVENT_LOOP = FeatureToggle("event_loop", True)


class SDPDevice(Device):
    """SDP Tango device base class."""

    # pylint: disable=attribute-defined-outside-init

    # ----------
    # Attributes
    # ----------

    version = attribute(
        label="Version",
        dtype=str,
        access=AttrWriteType.READ,
        doc="The version of the device",
    )

    # ---------------
    # General methods
    # ---------------

    def init_device(self):
        """Initialise the device."""
        super().init_device()

        # Enable change events on attributes
        self.set_change_event("State", True)

        # Initialise private values of attributes
        self._version = release.VERSION

    def delete_device(self):
        """Delete the device."""

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
        LOG.debug("Called _set_state %s -> %s", self.get_state().name, value.name)
        if self.get_state() != value:
            LOG.info("Setting device state to %s", value.name)
            self.set_state(value)
            self.push_change_event("State", self.get_state())

    @classmethod
    def _get_device_name(cls):
        # This gets the class name minus SDP e.g. Master
        return cls.__name__.split("SDP")[1]

    # ------------------
    # Event loop methods
    # ------------------

    def _start_event_loop(self):
        """Start event loop."""
        if FEATURE_EVENT_LOOP.is_active():
            # Start event loop in thread
            self._el_thread = threading.Thread(
                target=self._event_loop, name="EventLoop", daemon=True
            )
            self._el_watcher = None
            self._el_exit = False
            self._el_thread.start()
        else:
            # Add command to manually update attributes
            self._el_thread = None
            self._el_watcher = None
            self._el_exit = False
            cmd = command(f=self.update_attributes)
            self.add_command(cmd, True)

    def _stop_event_loop(self):
        """Stop event loop."""
        self._el_exit = True
        if self._el_watcher is not None:
            LOG.debug("Trigger watcher loop")
            self._el_watcher.trigger()
        if self._el_thread is not None:
            self._el_thread.join()
            self._el_thread = None

    def _event_loop(self):
        """Event loop to update attributes."""
        # Use EnsureOmniThread to make it thread-safe under Tango
        with EnsureOmniThread():
            LOG.info("Starting event loop")
            for watcher in self._config.watcher():
                # Expose watcher as an attribute so loop can be triggered
                # by another thread
                self._el_watcher = watcher
                LOG.debug("Watcher wake-up, exit %s", self._el_exit)
                if self._el_exit:
                    break
                # Use the Tango monitor lock to prevent attributes being
                # updated by this thread when a command is running
                with AutoTangoMonitor(self):
                    for txn in watcher.txn():
                        LOG.debug("Starting set attributes from config")
                        self._set_attr_from_config(txn)
                        LOG.debug("Finished set attributes from config")
            self._el_watcher = None
            LOG.info("Exiting event loop")

    def update_attributes(self):
        """
        Update the device attributes manually.

        This method is used during synchronous testing (when the event loop is
        not enabled).

        """
        LOG.info("Updating attributes")
        for txn in self._config.txn():
            self._set_attr_from_config(txn)

    def _update_attr_until_condition(self, condition: Callable):
        """
        Update attributes until condition is satisfied.

        This generic method is used by other methods to wait for specific
        conditions.

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

        This is used as a substitute event loop inside a command.

        :param values: list of state values

        """
        self._update_attr_until_condition(lambda: self.get_state() in values)

    def _set_attr_from_config(self, txn: Transaction) -> None:
        """
        Set attributes from configuration.

        This is called by the event loop. Subclasses override this method to
        set their state.

        :param txn: configuration transaction

        """
        raise NotImplementedError

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
            message = (
                f"Command {command_name} not allowed when "
                f"{attribute_name} is {value_message}"
            )
            origin = f"{type(self).__name__}.is_{command_name}_allowed()"
            raise_command_not_allowed(message, origin)

    def _command_allowed_state(self, command_name, allowed):
        """Check command is allowed in the current device state.

        :param command_name: name of the command
        :param allowed: list of allowed device state values

        """
        self._command_allowed(command_name, "device state", self.get_state(), allowed)
