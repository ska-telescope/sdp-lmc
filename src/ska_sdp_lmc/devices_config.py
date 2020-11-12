"""Config DB related tasks for SDP devices."""

import logging
from typing import Dict, List, Tuple, Optional

import tango
import ska_sdp_config
from .feature_toggle import FeatureToggle
from .tango_logging import set_transaction_id

FEATURE_CONFIG_DB = FeatureToggle('config_db', True)

LOG = logging.getLogger('ska_sdp_lmc')


def new_config_db():
    """Return a config DB object (factory function)."""
    backend = 'etcd3' if FEATURE_CONFIG_DB.is_active() else 'memory'
    logging.info("Using config DB %s backend", backend)
    config_db = ska_sdp_config.Config(backend=backend)
    return config_db


class DeviceConfig:
    """
    Base class to interact with configuration database.

    :param device_id: full device id
    :param sub_id: subarray id, if relevant
    """
    def __init__(self, device_id: str, sub_id: str = None):
        """Create the object."""
        self.db_client = new_config_db()
        self.device_id = device_id
        self._sub_id = sub_id
        self._txn_key = '/'+device_id+'/transaction_id'

    @property
    def id(self) -> str:
        """
        Get an id for this device.
        :return the sub-id if defined, otherwise the device id.
        """
        return self._sub_id if self._sub_id is not None else self.device_id

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

    @property
    def transaction_id(self) -> str:
        """
        Get the transaction id from the database.

        :returns: transaction id
        """
        txn_id = None
        for txn in self.txn():
            txn_id = self.get_transaction_id(txn)
        return txn_id

    def get_transaction_id(self, txn: ska_sdp_config.config.Transaction) -> str:
        """
        Get the transaction id from the database.

        :param txn: database transaction
        :returns: transaction id
        """
        txn_id = txn.raw.get(self._txn_key)
        return '' if txn_id is None else txn_id

    @transaction_id.setter
    def transaction_id(self, transaction_id: str) -> None:
        """
        Set the transaction in the DB.

        :param transaction_id: transaction id
        """
        # Inject id into the logging system.
        LOG.info('Set transaction id to %s', transaction_id)
        set_transaction_id(transaction_id)

        # Update the database.
        for txn in self.txn():
            try:
                txn.raw.update(self._txn_key, transaction_id)
            except ska_sdp_config.ConfigVanished:
                txn.raw.create(self._txn_key, transaction_id)


class MasterConfig(DeviceConfig):
    """Class to interact with master device configuration in DB."""
    def __init__(self):
        """Create the object."""
        super().__init__('master')

    @property
    def state(self) -> Optional[tango.DevState]:
        """
        Get the state from the database.

        :returns: tango device state
        """
        state = None
        for txn in self.txn():
            state = self.get_state(txn)
        return state

    @state.setter
    def state(self, state: tango.DevState) -> None:
        """
        Set the state in the DB.

        :param state: tango device state
        """
        state_dict = {'state': state.name.lower()}
        for txn in self.txn():
            try:
                txn.update_master(state_dict)
            except ska_sdp_config.ConfigVanished:
                txn.create_master(state_dict)

    @staticmethod
    def get_state(txn: ska_sdp_config.config.Transaction) -> Optional[tango.DevState]:
        """
        Get the state from the database.

        :param txn: database transaction
        :returns: tango device state
        """
        state = txn.get_master()['state'].upper()
        if state in tango.DevState.names:
            return tango.DevState.names[state]
        else:
            LOG.warning('Invalid state in db: %s', state)
            return None


class SubarrayConfig(DeviceConfig):
    """Class to interact with subarray configuration in DB."""
    def __init__(self, device_id, subarray_id):
        """Create the object."""
        super().__init__(device_id, sub_id=subarray_id)

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
            if self.id not in subarray_ids:
                txn.create_subarray(self.id, subarray)

    def create_sbi_pbs(self, subarray: Dict, sbi: Dict, pbs: List) -> None:
        """Create new SBI and PBs, and update subarray in config DB.

        :param subarray: update to subarray
        :param sbi: new SBI to create
        :param pbs: list of new PBs to create

        """
        for txn in self.txn():
            subarray_tmp = txn.get_subarray(self.id)
            subarray_tmp.update(subarray)
            txn.update_subarray(self.id, subarray_tmp)
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
            subarray_state = txn.get_subarray(self.id)
            sbi_id = subarray_state.get('sbi_id')
            if subarray:
                subarray_state.update(subarray)
                txn.update_subarray(self.id, subarray_state)
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
            subarray = txn.get_subarray(self.id)
            sbi_id = subarray.get('sbi_id')
            if sbi_id:
                sbi = txn.get_scheduling_block(sbi_id)
            else:
                sbi = {}

        return sbi
