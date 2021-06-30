"""Subarray device configuration interface."""

from typing import Any, Dict, List, Optional

from tango import DevState

from .attributes import ObsState
from .base_config import BaseConfig
from .exceptions import raise_command_failed


class SubarrayConfig(BaseConfig):
    """
    Subarray configuration interface.
    """

    def __init__(self, subarray_id: str):
        super().__init__()
        self._id = subarray_id

    def subarray(self, txn):
        """
        Create an instance of the subarray state interface for this subarray.

        :param txn: configuration transaction
        :returns: instance of the subarray state interface

        """
        return SubarrayState(txn, self._id)


class SubarrayState:
    """
    Subarray state interface.

    This wraps the transaction to provide a convenient interface for
    interacting with the subarray state in the configuration.

    :param txn: configuration transaction
    :param subarray_id: subarray number
    """

    # pylint: disable=too-many-instance-attributes

    def __init__(self, txn, subarray_id: str):
        self._txn = txn
        self._id = subarray_id

    def create_if_not_present(self, state: DevState, obs_state: ObsState):
        """
        Create subarray entry if it does not exist already.

        :param state: initial device state
        :param obs_state: initial observing state

        """
        subarray = self._txn.get_subarray(self._id)
        if subarray is None:
            subarray = {
                "transaction_id": None,
                "last_command": None,
                "state": state.name,
                "obs_state_target": obs_state.name,
                "sbi_id": None,
            }
            self._txn.create_subarray(self._id, subarray)

    def _get(self, name: str) -> Any:
        """
        Get item from subarray entry.

        :param name: the name of the item
        :returns: the value of the item, or None if not present

        """
        subarray = self._txn.get_subarray(self._id)
        return subarray.get(name)

    def _set(self, name: str, value: Any):
        """
        Set item in subarray entry.

        :param name: the name of the item
        :param value: the value to set

        """
        subarray = self._txn.get_subarray(self._id)
        subarray[name] = value
        self._txn.update_subarray(self._id, subarray)

    def _get_sbi(self, name: str) -> Any:
        """
        Get item from the SBI entry linked from the subarray.

        If no SBI is configured, this returns None.

        :param name: name of the item
        :returns: the value of the item, or None if not present

        """
        sbi_id = self._get("sbi_id")
        if sbi_id is not None:
            sbi = self._txn.get_scheduling_block(sbi_id)
            value = sbi.get(name)
        else:
            value = None
        return value

    def _set_sbi(self, name: str, value: Any):
        """
        Set item in the SBI entry linked from the subarray.

        If no SBI is configured, this does nothing.

        :param name: name of the item
        :param value: the value to set

        """
        sbi_id = self._get("sbi_id")
        if sbi_id is not None:
            sbi = self._txn.get_scheduling_block(sbi_id)
            sbi[name] = value
            self._txn.update_scheduling_block(sbi_id, sbi)

    @property
    def command(self) -> Optional[str]:
        """Command."""
        return self._get("last_command")

    @command.setter
    def command(self, value: Optional[str]):
        self._set("last_command", value)

    @property
    def transaction_id(self) -> Optional[str]:
        """Transaction ID."""
        return self._get("transaction_id")

    @transaction_id.setter
    def transaction_id(self, value: Optional[str]):
        self._set("transaction_id", value)

    @property
    def state(self) -> Optional[DevState]:
        """Device state."""
        value_str = self._get("state")
        if value_str in DevState.names:
            value = DevState.names[value_str]
        else:
            value = None
        return value

    @state.setter
    def state(self, value: DevState):
        self._set("state", value.name)

    @property
    def obs_state_target(self) -> Optional[ObsState]:
        """Target obsState."""
        value_str = self._get("obs_state_target")
        if value_str in ObsState.__members__:
            value = ObsState[value_str]
        else:
            value = None
        return value

    @obs_state_target.setter
    def obs_state_target(self, value: ObsState):
        self._set("obs_state_target", value.name)

    @property
    def scan_type(self) -> Optional[str]:
        """Scan type."""
        return self._get_sbi("current_scan_type")

    @scan_type.setter
    def scan_type(self, value: Optional[str]):
        if self._get("sbi_id") is not None and value is not None:

            # Check if scan type is in configuration
            scan_types = self._get_sbi("scan_types")
            st_ids = [st.get("id") for st in scan_types]
            if value not in st_ids:
                message = f"Scan type {value} is not defined"
                raise_command_failed(message, __name__)
        self._set_sbi("current_scan_type", value)

    @property
    def scan_id(self) -> Optional[int]:
        """Scan ID."""
        return self._get_sbi("scan_id")

    @scan_id.setter
    def scan_id(self, value: Optional[int]):
        self._set_sbi("scan_id", value)

    @property
    def receive_addresses(self) -> Optional[str]:
        """Receive addresses."""
        pb_id = self._get_sbi("pb_receive_addresses")
        if pb_id is not None:
            pb_state = self._txn.get_processing_block_state(pb_id)
            if pb_state is not None:
                return pb_state.get("receive_addresses")
        return None

    def create_sbi_and_pbs(self, sbi: Dict, pbs: List):
        """
        Create SBI and PBs.

        This creates the link from the subarray entry to the SBI entry.

        :param sbi: scheduling block instance
        :param pbs: list of processing blocks

        """
        sbi_id = sbi.get("id")
        # Create link from subarray to the SBI
        self._set("sbi_id", sbi_id)
        # Create the SBI.
        sbi_test = self._txn.get_scheduling_block(sbi_id)
        if sbi_test is not None:
            message = f"SBI {sbi_id} already exists"
            raise_command_failed(message, __name__)
        else:
            self._txn.create_scheduling_block(sbi_id, sbi)
        # Create link back from SBI to subarray
        self._set_sbi("subarray_id", self._id)
        # Create the PBs.
        for pblock in pbs:
            pb_test = self._txn.get_processing_block(pblock.id)
            if pb_test is not None:
                message = f"PB {pblock.id} already exists"
                raise_command_failed(message, __name__)
            else:
                self._txn.create_processing_block(pblock)

    def add_scan_types(self, new_scan_types: Optional[List]):
        """
        Add scan types to SBI.

        :param new_scan_types: list of new scan types to add to SBI

        """
        if new_scan_types is None:
            return
        scan_types = self._get_sbi("scan_types")

        # Check for redefinitions.
        st_ids = [st.get("id") for st in scan_types]
        for scan_type in new_scan_types:
            st_id = scan_type.get("id")
            if st_id in st_ids:
                message = f"Scan type {st_id} is already defined"
                raise_command_failed(message, __name__)
            else:
                st_ids.append(st_id)
                scan_types.append(scan_type)
        self._set_sbi("scan_types", scan_types)

    def finish_sbi(self):
        """
        Finish SBI.

        This ends the SBI and sets its status to FINISHED.

        """
        self._end_sbi("FINISHED")

    def cancel_sbi(self):
        """
        Cancel SBI.

        This ends the SBI and sets its status to CANCELLED.

        """
        self._end_sbi("CANCELLED")

    def _end_sbi(self, status: str):
        """
        End the SBI.

        This sets the status of the SBI, then removes the link from the
        subarray entry to the SBI entry in the configuration. Setting the
        status will signal to the real-time processing blocks that they should
        terminate. The SBI remains in the configuration but it will no longer
        be accessible from the subarray state interface.

        :param status: status to set in the SBI.

        """
        # Set SBI values before breaking the link.
        self._set_sbi("subarray_id", None)
        self._set_sbi("status", status)
        self.scan_type = None
        self.scan_id = None
        # This breaks the link
        self._set("sbi_id", None)
