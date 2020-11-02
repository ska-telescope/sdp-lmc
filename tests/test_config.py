from tango import DevState
from ska_sdp_lmc import devices_config, tango_logging


def test_transaction():
    dev = devices_config.DeviceConfig('test')
    dev.db_client.backend.delete(dev._txn_key, must_exist=False)
    assert dev.transaction_id == ''
    dev.transaction_id = 'xxx'
    assert dev.transaction_id == 'xxx'
    dev.transaction_id = 'yyy'
    assert dev.transaction_id == 'yyy'
    dev.db_client.backend.delete(dev._txn_key, must_exist=True)
    tango_logging.set_transaction_id('')


def test_master_state():
    master = devices_config.MasterConfig()
    master.db_client.backend.delete('/master', must_exist=False)
    assert master.device_id == 'master'
    master.state = DevState.OFF
    assert master.state == DevState.OFF
    master.state = DevState.ON
    assert master.state == DevState.ON
    for txn in master.db_client.txn():
        txn.update_master({'state': 'invalid'})
    assert master.state is None
    master.db_client.backend.delete('/master')

