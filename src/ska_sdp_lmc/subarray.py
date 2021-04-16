# -*- coding: utf-8 -*-
"""Tango SDPSubarray device module."""

import signal
import json
import sys

from tango import AttrWriteType, DevState
from tango.server import attribute, run

from ska_sdp_config.config import Transaction

# Note that relative imports are incompatible with main.
from ska_sdp_lmc.tango_logging import (
    get_logger, init_logger, log_transaction_id
)
from ska_sdp_lmc.attributes import AdminMode, HealthState, ObsState
from ska_sdp_lmc.base import SDPDevice
from ska_sdp_lmc.commands import command_transaction
from ska_sdp_lmc.subarray_config import SubarrayConfig
from ska_sdp_lmc.subarray_validation import (
    validate_assign_resources, validate_configure, validate_scan
)
from ska_sdp_lmc.util import terminate, check_args

LOG = get_logger()


class SDPSubarray(SDPDevice):
    """SDP Subarray device class."""

    # pylint: disable=invalid-name
    # pylint: disable=attribute-defined-outside-init
    # pylint: disable=too-many-public-methods

    # ----------
    # Attributes
    # ----------

    obsState = attribute(
        label='Observing state',
        dtype=ObsState,
        access=AttrWriteType.READ,
        doc='The device observing state.'
    )

    adminMode = attribute(
        label='Administration mode',
        dtype=AdminMode,
        access=AttrWriteType.READ_WRITE,
        doc='The device administration mode.'
    )

    healthState = attribute(
        label='Health state',
        dtype=HealthState,
        access=AttrWriteType.READ,
        doc='Subarray device health state.'
    )

    receiveAddresses = attribute(
        label='Receive addresses',
        dtype=str,
        access=AttrWriteType.READ,
        doc='Host addresses for the visibility receive workflow as a '
            'JSON string.'
    )

    scanType = attribute(
        label='Scan type',
        dtype=str,
        access=AttrWriteType.READ,
        doc='Scan type.'
    )

    scanID = attribute(
        label='Scan ID',
        dtype=int,
        access=AttrWriteType.READ,
        doc='Scan ID.',
        abs_change=1
    )

    # ---------------
    # General methods
    # ---------------

    def init_device(self):
        """Initialise the device."""
        init_logger(self)

        LOG.info('SDP Subarray initialising')
        super().init_device()
        self.set_state(DevState.INIT)

        # Enable change events on attributes
        self.set_change_event('obsState', True)
        self.set_change_event('adminMode', True)
        self.set_change_event('healthState', True)
        self.set_change_event('receiveAddresses', True)
        self.set_change_event('scanType', True)
        self.set_change_event('scanID', True)

        # Initialise private values of attributes
        self._obs_state = None
        self._admin_mode = None
        self._health_state = None
        self._receive_addresses = None
        self._scan_type = 'null'
        self._scan_id = 0

        # Set attributes not updated by event loop
        self._set_admin_mode(AdminMode.ONLINE)
        self._set_health_state(HealthState.OK)

        # Get connection to the config DB
        self._config = SubarrayConfig(self._get_subarray_id())

        # Create device state if it does not exist
        for txn in self._config.txn():
            subarray = self._config.subarray(txn)
            subarray.create_if_not_present(DevState.OFF, ObsState.EMPTY)

        # Start event loop
        self._start_event_loop()

        LOG.info('SDP Subarray initialised')

    # -----------------
    # Attribute methods
    # -----------------

    def read_obsState(self):
        """Get the obsState.

        :returns: the current obsState.

        """
        return self._obs_state

    def read_adminMode(self):
        """Get the adminMode.

        :returns: the current adminMode.

        """
        return self._admin_mode

    def read_healthState(self):
        """Get the healthState.

        :returns: the current healthState.

        """
        return self._health_state

    def read_receiveAddresses(self):
        """Get the receive addresses.

        :returns: JSON receive address map

        """
        return json.dumps(self._receive_addresses)

    def read_scanType(self):
        """Get the scan type.

        :returns: scan type ('null' = no scan type)

        """
        return self._scan_type

    def read_scanID(self):
        """Get the scan ID.

        :returns: scan ID (0 = no scan ID)

        """
        return self._scan_id

    def write_adminMode(self, admin_mode):
        """Set the adminMode.

        :param admin_mode: an admin mode enum value.

        """
        self._set_admin_mode(admin_mode)

    # --------
    # Commands
    # --------

    def is_On_allowed(self):
        """Check if the On command is allowed."""
        command_name = 'On'
        self._command_allowed_state(command_name, [DevState.OFF])
        self._command_allowed_obs_state(command_name, [ObsState.EMPTY])
        return True

    @command_transaction()
    def On(self, transaction_id: str):
        """
        Turn the subarray on.

        :param transaction_id: transaction ID

        """
        for txn in self._config.txn():
            subarray = self._config.subarray(txn)
            subarray.command = 'On'
            subarray.transaction_id = transaction_id
            subarray.state = DevState.ON
            subarray.obs_state_target = ObsState.EMPTY

    def is_Off_allowed(self):
        """Check if the Off command is allowed."""
        command_name = 'Off'
        self._command_allowed_state(command_name, [DevState.ON])
        return True

    @command_transaction()
    def Off(self, transaction_id: str):
        """
        Turn the subarray off.

        :param transaction_id: transaction ID

        """
        command_name = 'Off'
        if self._obs_state == ObsState.EMPTY:
            # This is a normal Off command.
            for txn in self._config.txn():
                subarray = self._config.subarray(txn)
                subarray.command = command_name
                subarray.transaction_id = transaction_id
                subarray.state = DevState.OFF
        else:
            # ObsState is not EMPTY, so cancel the scheduling block instance.
            LOG.info('obsState is not EMPTY')
            LOG.info('Cancelling the scheduling block instance')
            for txn in self._config.txn():
                subarray = self._config.subarray(txn)
                subarray.command = command_name
                subarray.transaction_id = transaction_id
                subarray.state = DevState.OFF
                subarray.obs_state_target = ObsState.EMPTY
                subarray.cancel_sbi()

    def is_AssignResources_allowed(self):
        """Check if the AssignResources command is allowed."""
        command_name = 'AssignResources'
        self._command_allowed_state(command_name, [DevState.ON])
        self._command_allowed_obs_state(command_name, [ObsState.EMPTY])
        return True

    @command_transaction(argdesc='resource configuration')
    def AssignResources(self, transaction_id: str, config: str):
        """
        Assign resources to the subarray.

        This creates the scheduling block instance and the processing blocks.

        :param transaction_id: transaction ID
        :param config: JSON string containing resource configuration

        """
        # Validate and parse the configuration
        sbi, pbs = validate_assign_resources(config)

        for txn in self._config.txn():
            subarray = self._config.subarray(txn)
            subarray.command = 'AssignResources'
            subarray.transaction_id = transaction_id
            subarray.obs_state_target = ObsState.IDLE
            subarray.create_sbi_and_pbs(sbi, pbs)

    def is_ReleaseResources_allowed(self):
        """Check if the ReleaseResources command is allowed."""
        command_name = 'ReleaseResources'
        self._command_allowed_state(command_name, [DevState.ON])
        self._command_allowed_obs_state(command_name, [ObsState.IDLE])
        return True

    @command_transaction()
    def ReleaseResources(self, transaction_id: str):
        """
        Release resources assigned to the subarray.

        This ends the scheduling block instance and its real-time processing
        blocks.

        :param transaction_id: transaction ID

        """
        for txn in self._config.txn():
            subarray = self._config.subarray(txn)
            subarray.command = 'ReleaseResources'
            subarray.transaction_id = transaction_id
            subarray.obs_state_target = ObsState.EMPTY
            subarray.finish_sbi()

    def is_Configure_allowed(self):
        """Check if the Configure command is allowed."""
        command_name = 'Configure'
        self._command_allowed_state(command_name, [DevState.ON])
        self._command_allowed_obs_state(command_name, [ObsState.IDLE,
                                                       ObsState.READY])
        return True

    @command_transaction(argdesc='scan type configuration')
    def Configure(self, transaction_id: str, config: str):
        """
        Configure scan type.

        :param transaction_id: transaction ID
        :param config: JSON string containing scan type configuration

        """
        # Validate and parse the configuration string
        new_scan_types, scan_type = validate_configure(config)

        for txn in self._config.txn():
            subarray = self._config.subarray(txn)
            subarray.command = 'Configure'
            subarray.transaction_id = transaction_id
            subarray.obs_state_target = ObsState.READY
            subarray.add_scan_types(new_scan_types)
            subarray.scan_type = scan_type

    def is_Scan_allowed(self):
        """Check if the Scan command is allowed."""
        command_name = 'Scan'
        self._command_allowed_state(command_name, [DevState.ON])
        self._command_allowed_obs_state(command_name, [ObsState.READY])
        return True

    @command_transaction(argdesc='scan ID')
    def Scan(self, transaction_id: str, config: str):
        """
        Start scan.

        :param transaction_id: transaction ID
        :param config: JSON string containing scan ID

        """
        # Validate and parse the configuration string
        scan_id = validate_scan(config)

        for txn in self._config.txn():
            subarray = self._config.subarray(txn)
            subarray.command = 'Scan'
            subarray.transaction_id = transaction_id
            subarray.obs_state_target = ObsState.SCANNING
            subarray.scan_id = scan_id

    def is_EndScan_allowed(self):
        """Check if the EndScan command is allowed."""
        command_name = 'EndScan'
        self._command_allowed_state(command_name, [DevState.ON])
        self._command_allowed_obs_state(command_name, [ObsState.SCANNING])
        return True

    @command_transaction()
    def EndScan(self, transaction_id: str):
        """
        End scan.

        :param transaction_id: transaction ID

        """
        for txn in self._config.txn():
            subarray = self._config.subarray(txn)
            subarray.command = 'EndScan'
            subarray.transaction_id = transaction_id
            subarray.obs_state_target = ObsState.READY
            subarray.scan_id = None

    def is_End_allowed(self):
        """Check if the End command is allowed."""
        command_name = 'End'
        self._command_allowed_state(command_name, [DevState.ON])
        self._command_allowed_obs_state(command_name, [ObsState.READY])
        return True

    @command_transaction()
    def End(self, transaction_id: str):
        """
        End.

        :param transaction_id: transaction ID

        """
        for txn in self._config.txn():
            subarray = self._config.subarray(txn)
            subarray.command = 'End'
            subarray.transaction_id = transaction_id
            subarray.obs_state_target = ObsState.IDLE
            subarray.scan_type = None

    def is_Abort_allowed(self):
        """Check if the Abort command is allowed."""
        command_name = 'Abort'
        self._command_allowed_state(command_name, [DevState.ON])
        self._command_allowed_obs_state(
            command_name,
            [ObsState.IDLE, ObsState.CONFIGURING, ObsState.READY,
             ObsState.SCANNING, ObsState.RESETTING]
        )
        return True

    @command_transaction()
    def Abort(self, transaction_id: str):
        """
        Abort the current activity.

        :param transaction_id: transaction ID

        """
        for txn in self._config.txn():
            subarray = self._config.subarray(txn)
            subarray.command = 'Abort'
            subarray.transaction_id = transaction_id
            subarray.obs_state_target = ObsState.ABORTED

    def is_ObsReset_allowed(self):
        """Check if the ObsReset command is allowed."""
        command_name = 'ObsReset'
        self._command_allowed_state(command_name, [DevState.ON])
        self._command_allowed_obs_state(command_name, [ObsState.ABORTED,
                                                       ObsState.FAULT])
        return True

    @command_transaction()
    def ObsReset(self, transaction_id: str):
        """
        Reset the subarray to the IDLE obsState.

        :param transaction_id: transaction ID

        """
        for txn in self._config.txn():
            subarray = self._config.subarray(txn)
            subarray.command = 'ObsReset'
            subarray.transaction_id = transaction_id
            subarray.obs_state_target = ObsState.IDLE
            subarray.scan_type = None
            subarray.scan_id = None


    def is_Restart_allowed(self):
        """Check if the Restart command is allowed."""
        command_name = 'Restart'
        self._command_allowed_state(command_name, [DevState.ON])
        self._command_allowed_obs_state(command_name, [ObsState.ABORTED,
                                                       ObsState.FAULT])
        return True

    @command_transaction()
    def Restart(self, transaction_id: str):
        """
        Restart the subarray in the EMPTY obsState.

        :param transaction_id: transaction ID

        """
        for txn in self._config.txn():
            subarray = self._config.subarray(txn)
            subarray.command = 'Restart'
            subarray.transaction_id = transaction_id
            subarray.obs_state_target = ObsState.EMPTY
            subarray.cancel_sbi()

    # ----------------------
    # Command allowed method
    # ----------------------

    def _command_allowed_obs_state(self, command_name, allowed):
        """
        Check if command is allowed in current obsState.

        :param command_name: name of the command
        :param allowed: list of allowed obsState values

        """
        self._command_allowed(command_name, 'obsState', self._obs_state,
                              allowed)

    # -------------------------
    # Attribute-setting methods
    # -------------------------

    def _set_obs_state(self, value):
        """Set obsState and push a change event."""
        LOG.info("obsState %s -> %s", self._obs_state, value)
        if self._obs_state != value:
            LOG.info('Setting obsState to %s', value.name)
            self._obs_state = value
            self.push_change_event('obsState', self._obs_state)

    def _set_admin_mode(self, value):
        """Set adminMode and push a change event."""
        if self._admin_mode != value:
            LOG.info('Setting adminMode to %s', value.name)
            self._admin_mode = value
            self.push_change_event('adminMode', self._admin_mode)

    def _set_health_state(self, value):
        """Set healthState and push a change event."""
        if self._health_state != value:
            LOG.info('Setting healthState to %s', value.name)
            self._health_state = value
            self.push_change_event('healthState', self._health_state)

    def _set_receive_addresses(self, value):
        """Set receiveAddresses and push a change event."""
        if self._receive_addresses != value:
            if value is None:
                LOG.info('Clearing receiveAddresses')
            else:
                LOG.info('Setting receiveAddresses')
            self._receive_addresses = value
            self.push_change_event('receiveAddresses',
                                   json.dumps(self._receive_addresses))

    def _set_scan_type(self, value):
        """Set scanType and push a change event."""
        if self._scan_type != value:
            LOG.info('Setting scanType to %s', value)
            self._scan_type = value
            self.push_change_event('scanType', self._scan_type)

    def _set_scan_id(self, value):
        """Set scanID and push a change event."""
        if self._scan_id != value:
            LOG.info('Setting scanID to %d', value)
            self._scan_id = value
            self.push_change_event('scanID', self._scan_id)

    # ------------------
    # Event loop methods
    # ------------------

    def _set_from_config(self, txn: Transaction) -> None:
        """
        Set attributes based on configuration.

        This is called from the event loop.

        :param txn: configuration transaction

        """
        subarray = self._config.subarray(txn)

        with log_transaction_id(subarray.transaction_id):
            self._set_state(subarray.state)
            self._set_receive_addresses(subarray.receive_addresses)
            self._set_scan_type(
                subarray.scan_type if subarray.scan_type else 'null'
            )
            self._set_scan_id(subarray.scan_id if subarray.scan_id else 0)

            if subarray.obs_state_target == ObsState.IDLE and \
                    subarray.command == 'AssignResources':
                if subarray.receive_addresses is None:
                    obs_state = ObsState.RESOURCING
                else:
                    obs_state = ObsState.IDLE
            else:
                obs_state = subarray.obs_state_target
            LOG.info("setting obsState to %s", obs_state)
            self._set_obs_state(obs_state)

    # ---------------
    # Utility methods
    # ---------------

    def _get_subarray_id(self):
        """
        Get subarray ID.

        The ID is the number of the subarray device, which is extracted from
        the device name.

        :returns: subarray ID

        """
        member = self.get_name().split('/')[2]
        number = member.split('_')[1]
        subarray_id = number.zfill(2)
        return subarray_id


def main(args=None, **kwargs):
    """Run server."""
    # Register SIGTERM handler.
    signal.signal(signal.SIGTERM, terminate)
    return run((SDPSubarray,), args=args, **kwargs)


if __name__ == '__main__':
    main(check_args(SDPSubarray, sys.argv))
