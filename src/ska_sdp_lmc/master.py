"""SDP Master Tango device module."""

import signal

from tango import AttrWriteType, DevState, LogLevel
from tango.server import attribute, command, run

from ska_sdp_config.config import Transaction

# Note that relative imports are incompatible with main.
from ska_sdp_lmc import tango_logging
from ska_sdp_lmc.attributes import HealthState
from ska_sdp_lmc.base import SDPDevice
from ska_sdp_lmc.devices_config import MasterConfig
from ska_sdp_lmc.util import terminate, log_command

LOG = tango_logging.get_logger()


class SDPMaster(SDPDevice):
    """SDP Master device class."""

    # pylint: disable=invalid-name
    # pylint: disable=attribute-defined-outside-init

    # ----------
    # Attributes
    # ----------

    healthState = attribute(
        label='Health state',
        dtype=HealthState,
        access=AttrWriteType.READ,
        doc='Master device health state'
    )

    # ---------------
    # General methods
    # ---------------

    def init_device(self):
        """Initialise the device."""
        super().init_device()
        self.set_state(DevState.INIT)
        LOG.info('Initialising SDP Master: %s', self.get_name())

        # Enable change events on attributes
        self.set_change_event('healthState', True)

        # Initialise private values of attributes
        self._health_state = None

        # Set attributes not updated by event loop
        self._set_health_state(HealthState.OK)

        # Get connection to the config DB
        self._config = MasterConfig()

        # Set initial device state
        self._config.state = DevState.STANDBY

        # Start event loop
        self._start_event_loop()
        LOG.info('SDP Master initialised: %s', self.get_name())

    # -----------------
    # Attribute methods
    # -----------------

    def read_healthState(self):
        """Read health state of the device.

        :return: Health state of the device
        """
        return self._health_state

    # --------
    # Commands
    # --------

    def is_On_allowed(self):
        """Check if the On command is allowed."""
        self._command_allowed_state(
            'On', [DevState.OFF, DevState.STANDBY, DevState.DISABLE]
        )
        return True

    @log_command
    @command()
    def On(self):
        """Turn the SDP on."""
        self._config.state = DevState.ON

    def is_Disable_allowed(self):
        """Check if the Disable command is allowed."""
        self._command_allowed_state(
            'Disable', [DevState.OFF, DevState.STANDBY, DevState.ON]
        )
        return True

    @log_command
    @command()
    def Disable(self):
        """Set the SDP to disable."""
        self._config.state = DevState.DISABLE

    def is_Standby_allowed(self):
        """Check if the Standby command is allowed."""
        self._command_allowed_state(
            'Standby', [DevState.OFF, DevState.DISABLE, DevState.ON]
        )
        return True

    @log_command
    @command()
    def Standby(self):
        """Set the SDP to standby."""
        self._config.state = DevState.STANDBY

    def is_Off_allowed(self):
        """Check if the Off command is allowed."""
        self._command_allowed_state(
            'Off', [DevState.STANDBY, DevState.DISABLE, DevState.ON]
        )
        return True

    @log_command
    @command()
    def Off(self):
        """Turn the SDP off."""
        self._config.state = DevState.OFF

    # This is called from the event loop.
    def _set_from_config(self, txn: Transaction) -> None:
        state = self._config.get_state(txn)
        if state is not None:
            self._set_state(state)

    # -------------------------
    # Attribute-setting methods
    # -------------------------

    def _set_health_state(self, value):
        """Set healthState and push a change event."""
        if self._health_state != value:
            LOG.debug('Setting healthState to %s', value.name)
            self._health_state = value
            self.push_change_event('healthState', self._health_state)


def main(args=None, **kwargs):
    """Run server."""
    # Initialise logging
    tango_logging.main(device_name='SDPMaster')

    # Register SIGTERM handler
    signal.signal(signal.SIGTERM, terminate)

    return run((SDPMaster,), args=args, **kwargs)


if __name__ == '__main__':
    main()
