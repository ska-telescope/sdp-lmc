"""SDP Master Tango device module."""

import signal
import sys

from tango import AttrWriteType, DevState
from tango.server import attribute, run

from ska_sdp_config.config import Transaction

# Note that relative imports are incompatible with main.
from ska_sdp_lmc.tango_logging import (
    get_logger, init_logger, log_transaction_id
)
from ska_sdp_lmc.attributes import HealthState
from ska_sdp_lmc.base import SDPDevice
from ska_sdp_lmc.commands import command_transaction
from ska_sdp_lmc.master_config import MasterConfig
from ska_sdp_lmc.util import terminate, check_args

LOG = get_logger()


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
        init_logger(self)

        LOG.info('SDP Master initialising')
        super().init_device()
        self.set_state(DevState.INIT)

        # Enable change events on attributes
        self.set_change_event('healthState', True)

        # Initialise private values of attributes
        self._health_state = None

        # Set attributes not updated by event loop
        self._set_health_state(HealthState.OK)

        # Get connection to the config DB
        self._config = MasterConfig()

        # Create device state if it does not exist
        for txn in self._config.txn():
            master = self._config.master(txn)
            master.create_if_not_present(DevState.STANDBY)

        # Start event loop
        self._start_event_loop()

        LOG.info('SDP Master initialised')

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

    @command_transaction()
    def On(self, transaction_id: str):
        """
        Turn the SDP on.

        :param transaction_id: transaction ID

        """
        for txn in self._config.txn():
            master = self._config.master(txn)
            master.transaction_id = transaction_id
            master.state = DevState.ON

    def is_Disable_allowed(self):
        """Check if the Disable command is allowed."""
        self._command_allowed_state(
            'Disable', [DevState.OFF, DevState.STANDBY, DevState.ON]
        )
        return True

    @command_transaction()
    def Disable(self, transaction_id: str):
        """
        Set the SDP to disable.

        :param transaction_id: transaction ID

        """
        for txn in self._config.txn():
            master = self._config.master(txn)
            master.transaction_id = transaction_id
            master.state = DevState.DISABLE

    def is_Standby_allowed(self):
        """Check if the Standby command is allowed."""
        self._command_allowed_state(
            'Standby', [DevState.OFF, DevState.DISABLE, DevState.ON]
        )
        return True

    @command_transaction()
    def Standby(self, transaction_id: str):
        """
        Set the SDP to standby.

        :param transaction_id: transaction ID

        """
        for txn in self._config.txn():
            master = self._config.master(txn)
            master.transaction_id = transaction_id
            master.state = DevState.STANDBY

    def is_Off_allowed(self):
        """Check if the Off command is allowed."""
        self._command_allowed_state(
            'Off', [DevState.STANDBY, DevState.DISABLE, DevState.ON]
        )
        return True

    @command_transaction()
    def Off(self, transaction_id: str):
        """
        Turn the SDP off.

        :param transaction_id: transaction ID

        """
        for txn in self._config.txn():
            master = self._config.master(txn)
            master.transaction_id = transaction_id
            master.state = DevState.OFF

    # ------------------
    # Event loop methods
    # ------------------

    def _set_from_config(self, txn: Transaction) -> None:
        """
        Set attributes from configuration.

        This is called from the event loop.

        :param txn: configuration transaction

        """
        master = self._config.master(txn)
        with log_transaction_id(master.transaction_id):
            self._set_state(master.state)

    # -------------------------
    # Attribute-setting methods
    # -------------------------

    def _set_health_state(self, value):
        """Set healthState and push a change event."""
        if self._health_state != value:
            LOG.info('Setting healthState to %s', value.name)
            self._health_state = value
            self.push_change_event('healthState', self._health_state)


def main(args=None, **kwargs):
    """Run server."""
    # Register SIGTERM handler
    signal.signal(signal.SIGTERM, terminate)
    return run((SDPMaster,), args=args, **kwargs)


if __name__ == '__main__':
    main(check_args(SDPMaster, sys.argv))
