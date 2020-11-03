from tango import DevState
from ska_sdp_lmc import devices_config


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

