"""Master device configuration interface."""
from typing import Any, Optional

from tango import DevState

from .base_config import BaseConfig


class MasterConfig(BaseConfig):
    """
    Master configuration interface.
    """

    def __init__(self):
        super().__init__()

    def master(self, txn):
        """
        Create an instance of the master state interface.

        :param txn: configuration transaction
        :returns: instance of the master state interface

        """
        # pylint: disable=no-self-use
        return MasterState(txn)


class MasterState:
    """
    Master state interface.

    This wraps the transaction to provide a convenient interface for
    interacting with the master state in the configuration.

    :param txn: configuration transaction.
    """

    def __init__(self, txn):
        self._txn = txn

    def create_if_not_present(self, state: DevState):
        """
        Create master entry if it does not exist already.

        :param state: initial device state

        """
        master = self._txn.get_master()
        if master is None:
            master = {
                'transaction_id': None,
                'state': state.name
            }
            self._txn.create_master(master)

    def _get(self, name: str) -> Optional[Any]:
        """
        Get item from master entry.

        :param name: the name of the item
        :returns: the value of the item, or None if not present

        """
        master = self._txn.get_master()
        return None if master is None else master.get(name)

    def _set(self, name: str, value: Any):
        """
        Set item in master entry.

        :param name: the name of the item
        :param value: the value to set

        """
        master = self._txn.get_master()
        master[name] = value
        self._txn.update_master(master)

    @property
    def state(self) -> Optional[DevState]:
        """Device state."""
        value_str = self._get('state')
        if value_str in DevState.names:
            value = DevState.names[value_str]
        else:
            value = None
        return value

    @state.setter
    def state(self, state: DevState):
        self._set('state', state.name)

    @property
    def transaction_id(self) -> str:
        """Transaction ID."""
        return self._get('transaction_id')

    @transaction_id.setter
    def transaction_id(self, transaction_id: str):
        self._set('transaction_id', transaction_id)
