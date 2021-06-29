# coding: utf-8
"""Test for master and subarray config."""
# pylint: disable=protected-access
# pylint: disable=invalid-name
# pylint: disable=too-many-branches
# pylint: disable=too-many-statements

from tango import DevState
from ska_sdp_config import ProcessingBlock
from ska_sdp_lmc import master_config, subarray_config
from ska_sdp_lmc.attributes import ObsState


def test_master_config():
    """Test master device configuration interface."""
    config = master_config.MasterConfig()
    config._client.backend.delete("/master", must_exist=False)

    # Initialisation
    for txn in config.txn():
        master = config.master(txn)
        master.create_if_not_present(DevState.STANDBY)

    for txn in config.txn():
        master = config.master(txn)
        assert master.transaction_id is None
        assert master.state == DevState.STANDBY

    # Set transaction ID and device state
    for txn in config.txn():
        master = config.master(txn)
        master.transaction_id = "aaa"
        master.state = DevState.ON

    for txn in config.txn():
        master = config.master(txn)
        assert master.transaction_id == "aaa"
        assert master.state == DevState.ON

    # Test invalid device state

    for txn in config.txn():
        # Use low-level master interface
        master = txn.get_master()
        master["state"] = "invalid"
        txn.update_master(master)

    for txn in config.txn():
        master = config.master(txn)
        assert master.state is None

    config._client.backend.delete("/master")


def test_subarray_config():
    """Test subarray device configuration interface."""
    subarray_id = "01"
    config = subarray_config.SubarrayConfig(subarray_id)
    config._client.backend.delete("/subarray", must_exist=False, recursive=True)
    config._client.backend.delete("/sb", must_exist=False, recursive=True)
    config._client.backend.delete("/pb", must_exist=False, recursive=True)

    # Initialisation
    for txn in config.txn():
        subarray = config.subarray(txn)
        subarray.create_if_not_present(DevState.OFF, ObsState.EMPTY)

    for txn in config.txn():
        subarray = config.subarray(txn)
        assert subarray.command is None
        assert subarray.transaction_id is None
        assert subarray.state == DevState.OFF
        assert subarray.obs_state_target == ObsState.EMPTY
        assert subarray.scan_type is None
        assert subarray.scan_id is None
        assert subarray.receive_addresses is None

    # Set attributes
    for txn in config.txn():
        subarray = config.subarray(txn)
        subarray.command = "command_aaa"
        subarray.transaction_id = "txn-aaa"
        subarray.state = DevState.ON
        subarray.obs_state_target = ObsState.IDLE
        # scan_type and scan_id should be ignored, because no SBI is configured
        subarray.scan_type = "xxx"
        subarray.scan_id = 123

    for txn in config.txn():
        subarray = config.subarray(txn)
        assert subarray.command == "command_aaa"
        assert subarray.transaction_id == "txn-aaa"
        assert subarray.state == DevState.ON
        assert subarray.obs_state_target == ObsState.IDLE
        assert subarray.scan_type is None
        assert subarray.scan_id is None
        assert subarray.receive_addresses is None

    # Create first SBI and its PBs
    for txn in config.txn():
        subarray = config.subarray(txn)
        sbi, pbs = fake_sbi_and_pbs("xxx")
        subarray.create_sbi_and_pbs(sbi, pbs)

    for txn in config.txn():
        subarray = config.subarray(txn)
        assert subarray.scan_type is None
        assert subarray.scan_id is None
        assert subarray.receive_addresses is None
        # Use low-level SBI interface to check SBI
        sbi = txn.get_scheduling_block("eb-xxx")
        assert sbi["subarray_id"] == subarray_id
        assert sbi["status"] == "ACTIVE"

    # Select scan type and set scan ID
    for txn in config.txn():
        subarray = config.subarray(txn)
        subarray.add_scan_types(None)
        subarray.scan_type = "yyy"
        subarray.scan_id = 456

    for txn in config.txn():
        subarray = config.subarray(txn)
        assert subarray.scan_type == "yyy"
        assert subarray.scan_id == 456

    # Finish SBI
    for txn in config.txn():
        subarray = config.subarray(txn)
        subarray.finish_sbi()

    for txn in config.txn():
        subarray = config.subarray(txn)
        assert subarray.scan_type is None
        assert subarray.scan_id is None
        assert subarray.receive_addresses is None
        # Use low-level SBI interface to check SBI
        sbi = txn.get_scheduling_block("eb-xxx")
        assert sbi["subarray_id"] is None
        assert sbi["status"] == "FINISHED"

    # Create second SBI and its PBs
    for txn in config.txn():
        subarray = config.subarray(txn)
        sbi, pbs = fake_sbi_and_pbs("yyy")
        subarray.create_sbi_and_pbs(sbi, pbs)

    for txn in config.txn():
        subarray = config.subarray(txn)
        assert subarray.scan_type is None
        assert subarray.scan_id is None
        assert subarray.receive_addresses is None

        # Use low-level SBI interface to check SBI
        sbi = txn.get_scheduling_block("eb-yyy")
        assert sbi["subarray_id"] == subarray_id
        assert sbi["status"] == "ACTIVE"

    # Add a new scan type, select it and set scan ID
    for txn in config.txn():
        subarray = config.subarray(txn)
        subarray.add_scan_types([{"id": "zzz"}])
        subarray.scan_type = "zzz"
        subarray.scan_id = 789

    for txn in config.txn():
        subarray = config.subarray(txn)
        assert subarray.scan_type == "zzz"
        assert subarray.scan_id == 789

    # Cancel SBI
    for txn in config.txn():
        subarray = config.subarray(txn)
        subarray.cancel_sbi()

    for txn in config.txn():
        subarray = config.subarray(txn)
        assert subarray.scan_type is None
        assert subarray.scan_id is None
        assert subarray.receive_addresses is None
        # Use low-level SBI interface to check SBI
        sbi = txn.get_scheduling_block("eb-yyy")
        assert sbi["subarray_id"] is None
        assert sbi["status"] == "CANCELLED"

    # Test invalid state and obsState values
    for txn in config.txn():
        # Use low-level subarray interface to set invalid state and obs_state
        subarray = txn.get_subarray(subarray_id)
        subarray["state"] = "invalid"
        subarray["obs_state_target"] = "invalid"
        txn.update_subarray(subarray_id, subarray)

    for txn in config.txn():
        subarray = config.subarray(txn)
        assert subarray.state is None
        assert subarray.obs_state_target is None

    config._client.backend.delete("/subarray", must_exist=False, recursive=True)
    config._client.backend.delete("/sb", must_exist=False, recursive=True)
    config._client.backend.delete("/pb", must_exist=False, recursive=True)


def fake_sbi_and_pbs(name):
    """Generate fake scheduling block instance and processing blocks."""
    eb_id = "eb-" + name
    pb_id = "pb-" + name
    sbi = {
        "id": eb_id,
        "subarray_id": None,
        "pb_receive_addresses": pb_id,
        "scan_types": [{"id": "xxx"}, {"id": "yyy"}],
        "current_scan_type": None,
        "scan_id": None,
        "status": "ACTIVE",
    }

    # Temporary - configdb currently don't support new schema
    workflow = {"type": "realtime", "id": "test_workflow", "version": "0.1.0"}
    pb = ProcessingBlock(pb_id, eb_id, workflow, parameters={}, dependencies=[])
    return sbi, [pb]
