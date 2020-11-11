import sys
from tango import DevState
from ska_sdp_lmc import devices_config, tango_logging


def test_transaction():
    print(f'*** path {sys.path}')
    dev = devices_config.DeviceConfig('test')
    print(f'*** backend {dev.db_client.backend.__module__}')
    dev.db_client.backend.delete(dev._txn_key, must_exist=False)
    assert dev.transaction_id == ''
    dev.transaction_id = 'xxx'
    assert dev.transaction_id == 'xxx'
    dev.transaction_id = 'yyy'
    assert dev.transaction_id == 'yyy'
    print(f'backend before {dev.db_client.backend}')
    dev.db_client.backend.delete(dev._txn_key, must_exist=True)
    print(f'backend after {dev.db_client.backend}')
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
    print(f'backend before {master.db_client.backend}')
    master.db_client.backend.delete('/master')
    print(f'backend after {master.db_client.backend}')

