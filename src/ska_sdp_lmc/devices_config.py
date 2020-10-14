"""Config DB related tasks for SDP devices."""

import logging
from typing import Dict, List, Tuple, Optional

import tango
import ska_sdp_config
from .feature_toggle import FeatureToggle

FEATURE_CONFIG_DB = FeatureToggle('config_db', True)

LOG = logging.getLogger('ska_sdp_lmc')


def new_config_db():
    """Return a config DB object (factory function)."""
    backend = 'etcd3' if FEATURE_CONFIG_DB.is_active() else 'memory'
    logging.info("Using config DB %s backend", backend)
    config_db = ska_sdp_config.Config(backend=backend)
    return config_db


class DeviceConfig:
    """Base class to interact with configuration database."""
    def __init__(self, device_id):
        """Create the object."""
        self.db_client = new_config_db()
        self.device_id = device_id

    def _lock(self) -> None:
        """Synchronize placeholder."""

    def _unlock(self) -> None:
        """Synchronize placeholder."""

    def txn(self):
        """
        Convenience method to create a transaction.

        :returns: transaction
        """
        return self.db_client.txn()


class MasterConfig(DeviceConfig):
    """Class to interact with master device configuration in DB."""
    def __init__(self):
        """Create the object."""
        super().__init__('/master')

    def set_state(self, state: tango.DevState) -> None:
        """
        Set the state in the DB.

        :param state: tango device state
        """
        # Probably should update config db api for this.
        # For now at least, use the raw transaction directly.
        state_str = state.name.lower()
        for txn in self.txn():
            try:
                txn.raw.update(self.device_id, state_str)
            except ska_sdp_config.ConfigVanished:
                txn.raw.create(self.device_id, state_str)

    def get_state(self, txn: ska_sdp_config.config.Transaction) -> tango.DevState:
        """
        Get the state from the database.

        :param txn: database transaction
        :returns: tango device state
        """
        state = txn.raw.get(self.device_id)
        return tango.DevState.names[state.upper()]


class SubarrayConfig(DeviceConfig):
    """Class to interact with subarray configuration in DB."""
    def __init__(self, subarray_id):
        """Create the object."""
        super().__init__(subarray_id)

    # pylint: disable=invalid-name

    def init_subarray(self, subarray: Dict) -> None:
        """Initialise subarray in config DB.

        If the subarray entry exists already it is not overwritten: it is
        assumed that this is the existing state that should be resumed. If the
        subarray entry does not exist, it is initialised with device state OFF
        and obsState EMPTY.

        """
        for txn in self.txn():
            subarray_ids = txn.list_subarrays()
            if self.device_id not in subarray_ids:
                txn.create_subarray(self.device_id, subarray)

    def create_sbi_pbs(self, subarray: Dict, sbi: Dict, pbs: List) -> None:
        """Create new SBI and PBs, and update subarray in config DB.

        :param subarray: update to subarray
        :param sbi: new SBI to create
        :param pbs: list of new PBs to create

        """
        for txn in self.txn():
            subarray_tmp = txn.get_subarray(self.device_id)
            subarray_tmp.update(subarray)
            txn.update_subarray(self.device_id, subarray_tmp)
            sbi_id = sbi.get('id')
            txn.create_scheduling_block(sbi_id, sbi)
            for pb in pbs:
                txn.create_processing_block(pb)

    def update_subarray_sbi(self, subarray: Optional[Dict] = None,
                            sbi: Optional[Dict] = None) -> None:
        """Update subarray and SBI in config DB.

        :param subarray: update to subarray (optional)
        :param sbi: update to SBI (optional)

        """
        for txn in self.txn():
            subarray_state = txn.get_subarray(self.device_id)
            sbi_id = subarray_state.get('sbi_id')
            if subarray:
                subarray_state.update(subarray)
                txn.update_subarray(self.device_id, subarray_state)
            if sbi and sbi_id:
                sbi_state = txn.get_scheduling_block(sbi_id)
                sbi_state.update(sbi)
                txn.update_scheduling_block(sbi_id, sbi_state)

    def list_sbis_pbs(self) -> Tuple[List, List]:
        """Get existing SBI and PB IDs from config DB.

        :returns: list of SBI IDs and list of PB IDs

        """
        for txn in self.txn():
            sbi_ids = txn.list_scheduling_blocks()
            pb_ids = txn.list_processing_blocks()

        return sbi_ids, pb_ids

    def get_sbi(self) -> Dict:
        """Get SBI from config DB.

        :returns: SBI

        """
        for txn in self.txn():
            subarray = txn.get_subarray(self.device_id)
            sbi_id = subarray.get('sbi_id')
            if sbi_id:
                sbi = txn.get_scheduling_block(sbi_id)
            else:
                sbi = {}

        return sbi
