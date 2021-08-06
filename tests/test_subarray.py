# coding: utf-8
"""SDP Subarray device tests."""
# pylint: disable=invalid-name
# pylint: disable=redefined-outer-name
# pylint: disable=protected-access
# pylint: disable=fixme


import os
import json
import tango

from ska_telmodel.schema import validate
from ska_telmodel.sdp.version import SDP_RECVADDRS_PREFIX

from pytest_bdd import given, parsers, scenarios, then, when

import ska_sdp_config

from . import device_utils
from ska_sdp_lmc import (
    AdminMode,
    HealthState,
    ObsState,
    util,
    base_config,
    tango_logging,
)

CONFIG_DB_CLIENT = base_config.new_config_db_client()
SUBARRAY_ID = "01"
RECEIVE_WORKFLOWS = ["test_receive_addresses"]
DEVICE_NAME = "test_sdp/elt/subarray_1"
SCHEMA_VERSION = "0.3"
LOG = tango_logging.get_logger()

# -----------------------------------------------------------------------------
# Scenarios : Specify what we want the software to do
# -----------------------------------------------------------------------------

# Load scenarios from the specified feature file.
scenarios("features/subarray.feature")


# -----------------------------------------------------------------------------
# Given steps: set the initial context of the system
# -----------------------------------------------------------------------------


@given("I have an SDPSubarray device", target_fixture="subarray_device")
def subarray_device(devices):
    """Get the SDPSubarray device proxy.

    :param devices: the devices in a MultiDeviceTestContext

    """
    device = device_utils.init_device(devices, DEVICE_NAME, wipe_config_db)
    device_utils.Monitor.close_all()
    device_utils.Monitor(device, "State")
    device_utils.Monitor(device, "obsState")
    return device


@given(parsers.parse("the state is {state:S}"))
@given("the state is <initial_state>")
def set_subarray_device_state(subarray_device, state: str):
    """Set the device state to the specified value.

    This function sets the obsState to EMPTY.

    :param subarray_device: an SDPSubarray device.
    :param state: an SDPSubarray state string.

    """
    # Set the device state in the config DB
    with util.LOCK:
        set_state_and_obs_state(state, "EMPTY")

    # Wait for the device state to update.
    LOG.info("Set state: wait for updates")
    device_utils.wait_for_values(
        subarray_device, ["State", "obsState"], [state, str(ObsState.EMPTY.value)]
    )

    # Check that state has been set correctly
    assert subarray_device.state() == tango.DevState.names[state]


@given(parsers.parse("obsState is {initial_obs_state:S}"))
@given("obsState is <initial_obs_state>")
def set_subarray_device_obstate(subarray_device, initial_obs_state: str):
    """Set the obsState to the specified value.

    This function sets the device state to ON.

    :param subarray_device: an SDPSubarray device
    :param initial_obs_state: an SDPSubarray ObsState enum string

    """
    # Set the obsState in the config DB
    state = "ON"
    set_state_and_obs_state(state, initial_obs_state)

    # Wait for the device state to update.
    LOG.info("Set obsState: wait for updates")
    device_utils.wait_for_values(
        subarray_device,
        ["obsState"],
        [str(ObsState[initial_obs_state].value)],
    )

    # Check obsState has been set correctly
    assert subarray_device.ObsState == ObsState[initial_obs_state]


# -----------------------------------------------------------------------------
# When steps: describe an event or action
# -----------------------------------------------------------------------------


@when(parsers.parse("I call {command:S}"))
@when("I call <command>")
def call_command(subarray_device, command):
    """Call an SDPSubarray command.

    :param subarray_device: an SDPSubarray device
    :param command: the name of the command

    """
    # Check command is present
    command_list = subarray_device.get_command_list()
    assert command in command_list

    # Get information about the command
    command_config = subarray_device.get_command_config(command)

    # Get the command argument
    if command_config.in_type == tango.DevVoid:
        config_str = None
    elif command_config.in_type == tango.DevString:
        config_str = read_command_argument(command)
    else:
        message = "Cannot handle command with argument type {}"
        raise ValueError(message.format(command_config.in_type))

    try:
        # Call the command
        subarray_device.command_inout(command, cmd_param=config_str)
        subarray_device.exception = None

        # Wait for the device state to update
        LOG.info(
            f"Called {command}: wait for changes, "
            f"obs state {ObsState(subarray_device.obsState.value).name}"
        )
        device_utils.wait_for_changes(subarray_device, ["State", "obsState"])
        # device_utils.wait_for_changes(subarray_device, ["obsState"])
        LOG.info(f"obs state is now {ObsState(subarray_device.obsState.value).name}")

    except tango.DevFailed as e:
        subarray_device.exception = e


@when("I call <command> without an interface value in the JSON configuration")
def call_command_without_interface(subarray_device, command):
    """Call an SDPSubarray command without an interface value.

    :param subarray_device: an SDPSubarray device
    :param command: the name of the command

    """
    # Check command is present
    command_list = subarray_device.get_command_list()
    assert command in command_list

    # Get previous version of the command argument and delete the interface
    # value
    config = read_command_argument(command, previous=True, decode=True)
    del config["interface"]

    try:
        # Call the command
        subarray_device.command_inout(command, cmd_param=json.dumps(config))
        subarray_device.exception = None

        # Wait for the device state to update
        LOG.info("Called command without value: wait for changes")
        device_utils.wait_for_changes(subarray_device, ["obsState"])

    except tango.DevFailed as e:
        subarray_device.exception = e


@when("I call <command> with previous JSON configuration")
def call_command_with_previous_config(subarray_device, command):
    """Call an SDPSubarray command without an interface value.

    :param subarray_device: an SDPSubarray device
    :param command: the name of the command

    """
    # Check command is present
    command_list = subarray_device.get_command_list()
    assert command in command_list

    # Get previous version of the command argument
    config_str = read_command_argument(command, previous=True)

    try:
        # Call the command
        subarray_device.command_inout(command, cmd_param=config_str)
        subarray_device.exception = None

        # Wait for the device state to update
        LOG.info("Called command without value: wait for changes")
        device_utils.wait_for_changes(subarray_device, ["obsState"])

    except tango.DevFailed as e:
        subarray_device.exception = e


@when("I call <command> with an invalid JSON configuration")
def call_command_with_invalid_json(subarray_device, command):
    """Call an SDPSubarray command without an interface value.

    :param subarray_device: an SDPSubarray device
    :param command: the name of the command

    """
    # Check command is present
    command_list = subarray_device.get_command_list()
    assert command in command_list

    # Read an invalid command argument
    config_str = read_command_argument(command, invalid=True)

    # Call the command
    try:
        subarray_device.command_inout(command, cmd_param=config_str)
        subarray_device.exception = None
    except tango.DevFailed as e:
        subarray_device.exception = e


@when("the receive processing block writes the receive addresses into its state")
def receive_addresses_written(subarray_device):
    receive_addresses = read_receive_addresses()

    with util.LOCK:
        for txn in CONFIG_DB_CLIENT.txn():
            pb_list = txn.list_processing_blocks()
            for pb_id in pb_list:
                pb = txn.get_processing_block(pb_id)
                if pb.workflow["id"] in RECEIVE_WORKFLOWS:
                    pb_state = txn.get_processing_block_state(pb_id)
                    pb_state["receive_addresses"] = receive_addresses
                    txn.update_processing_block_state(pb_id, pb_state)

    LOG.info("Receive addresses: wait for transition to idle")
    device_utils.wait_for_values(
        subarray_device, ["obsState"], [str(ObsState.IDLE.value)]
    )
    LOG.info(f"obs state is now {ObsState(subarray_device.obsState.value).name}")


# -----------------------------------------------------------------------------
# Then steps: check the outcome is as expected
# -----------------------------------------------------------------------------


@then(parsers.parse("the state should be {expected:S}"))
def device_state_equals(subarray_device, expected):
    """Check the Subarray device device state.

    :param subarray_device: an SDPSubarray device.
    :param expected: the expected device state.
    """
    assert subarray_device.state() == tango.DevState.names[expected]


@then(parsers.parse("obsState should become {final_obs_state:S}"))
@then(parsers.parse("obsState should be {final_obs_state:S}"))
@then("obsState should become <final_obs_state>")
@then("obsState should be <final_obs_state>")
def obs_state_equals(subarray_device, final_obs_state):
    """Check the Subarray obsState attribute value.

    :param subarray_device: an SDPSubarray device.
    :param final_obs_state: the expected obsState.
    """
    assert subarray_device.obsState == ObsState[final_obs_state]


@then(parsers.parse("adminMode should be {admin_mode:S}"))
def admin_mode_equals(subarray_device, admin_mode):
    """Check the Subarray adminMode value.

    :param subarray_device: An SDPSubarray device.
    :param admin_mode: The expected adminMode.
    """
    assert subarray_device.adminMode == AdminMode[admin_mode]


@then(parsers.parse("healthState should be {health_state:S}"))
def health_state_equals(subarray_device, health_state):
    """Check the Subarray healthState value.

    :param subarray_device: An SDPSubarray device.
    :param health_state: The expected heathState.
    """
    assert subarray_device.healthState == HealthState[health_state]


@then("the input type of <command> should be <input_type>")
def command_input_type_equals(subarray_device, command, input_type):
    """Check input type of a command.

    :param subarray_device: an SDPSubarray device
    :param command: the command name
    :param input_type: the expected input type

    """
    assert command in subarray_device.get_command_list()
    command_config = subarray_device.get_command_config(command)
    assert command_config.in_type == getattr(tango, input_type)


@then("the output type of <command> should be <output_type>")
def command_output_type_equals(subarray_device, command, output_type):
    """Check output type of a command.

    :param subarray_device: an SDPSubarray device.
    :param command: the command name
    :param output_type: the expected output type

    """
    assert command in subarray_device.get_command_list()
    command_config = subarray_device.get_command_config(command)
    assert command_config.out_type == getattr(tango, output_type)


@then("the device should raise tango.DevFailed")
def command_raises_dev_failed(subarray_device):
    """Check that calling command raises a tango.DevFailed error.

    :param subarray_device: An SDPSubarray device.
    """
    e = subarray_device.exception
    assert e is not None and isinstance(e, tango.DevFailed)


@then("the processing blocks should be in the config DB")
def processing_blocks_in_config_db():
    """Check that the config DB has the configured PBs.

    :param subarray_device: An SDPSubarray device.

    """
    # Get the expected processing blocks from the AssignResources argument
    _, pbs = get_sbi_pbs()
    # Check they are present in the config DB
    for txn in CONFIG_DB_CLIENT.txn():
        pb_ids = txn.list_processing_blocks()
        for pb_expected in pbs:
            assert pb_expected.id in pb_ids
            pb = txn.get_processing_block(pb_expected.id)
            assert pb == pb_expected


@then("receiveAddresses should have the expected value")
def receive_addresses_expected(subarray_device):
    """Check that the receiveAddresses value is as expected.

    :param subarray_device: An SDPSubarray device.

    """
    recvaddrs_schema = SDP_RECVADDRS_PREFIX + SCHEMA_VERSION

    # Get the expected receive addresses from the data file
    receive_addresses_expected = read_receive_addresses()
    receive_addresses = json.loads(subarray_device.receiveAddresses)
    assert receive_addresses == receive_addresses_expected
    validate(recvaddrs_schema, receive_addresses, 2)

    # With interface version given as part of JSON object
    receive_addresses["interface"] = recvaddrs_schema
    validate(None, receive_addresses, 2)


@then("receiveAddresses should be an empty JSON object")
def receive_addresses_empty(subarray_device):
    """Check that the receiveAddresses value is an empty JSON object.

    :param subarray_device: An SDPSubarray device.

    """
    receive_addresses = json.loads(subarray_device.receiveAddresses)
    assert receive_addresses is None


@then("the log should not contain a transaction ID")
def log_contains_no_transaction_id():
    """Check that the log does not contain a transaction ID."""
    assert not device_utils.LOG_LIST.text_in_tag("txn-", last=5)


@then("the log should contain a transaction ID")
def log_contains_transaction_id():
    """Check that the log does contain a transaction ID."""
    # Allow some scope for some additional messages afterwards.
    assert device_utils.LOG_LIST.text_in_tag("txn-", last=5)


# -----------------------------------------------------------------------------
# Ancillary functions
# -----------------------------------------------------------------------------


def wipe_config_db():
    """Remove all entries in the config DB."""
    CONFIG_DB_CLIENT.backend.delete("/pb", must_exist=False, recursive=True)
    CONFIG_DB_CLIENT.backend.delete("/sb", must_exist=False, recursive=True)
    CONFIG_DB_CLIENT.backend.delete("/subarray", must_exist=False, recursive=True)
    tango_logging.set_transaction_id("")


def set_state_and_obs_state(state, obs_state):
    """Set state and obsState in the config DB.

    This updates the subarray entry and creates the SBI and PBs if they are
    present in the desired obsState.

    """
    # Check state and obsState are valid values
    assert state in tango.DevState.names
    assert obs_state in ObsState.__members__

    if obs_state == "RESOURCING":
        # Transitional obs_state: target is IDLE, but receive workflow has not
        # written receive addresses into PB state.
        obs_state_target = "IDLE"
    else:
        obs_state_target = obs_state

    if obs_state == "EMPTY":
        # No SBI or PBs associated with subarray
        sbi_id = None
        sbi = {}
        pbs = []
    else:
        sbi, pbs = get_sbi_pbs()
        sbi_id = sbi.get("id")

    if obs_state in ["READY", "SCANNING"]:
        scan_type = get_scan_type()
    else:
        scan_type = None

    if obs_state == "SCANNING":
        scan_id = get_scan_id()
    else:
        scan_id = None

    subarray = {
        "state": state,
        "obs_state_target": obs_state_target,
        "sbi_id": sbi_id,
        "last_command": None,
    }
    sbi["scan_type"] = scan_type
    sbi["scan_id"] = scan_id

    for txn in CONFIG_DB_CLIENT.txn():
        txn.update_subarray(SUBARRAY_ID, subarray)
        if sbi_id is not None:
            txn.create_scheduling_block(sbi_id, sbi)
        for pb in pbs:
            txn.create_processing_block(pb)

    if obs_state == "RESOURCING":
        # Create PB states without receive addresses
        create_pb_states(recvaddrs=False)
    elif obs_state != "EMPTY":
        # Create PB states with receive addresses
        create_pb_states(recvaddrs=True)


def create_pb_states(recvaddrs=True):
    """
    Create PB states in the config DB.

    This creates the PB states with status = RUNNING. If required, it adds the
    receive addresses to the state of any workflow matching the list of receive
    workflows.

    :param recvaddrs: write receive addresses into receive workflow PB states

    """
    receive_addresses = read_receive_addresses()

    for txn in CONFIG_DB_CLIENT.txn():
        pb_list = txn.list_processing_blocks()
        for pb_id in pb_list:
            pb_state = txn.get_processing_block_state(pb_id)
            if pb_state is None:
                pb_state = {"status": "RUNNING"}
                pb = txn.get_processing_block(pb_id)
                if pb.workflow["id"] in RECEIVE_WORKFLOWS:
                    sbi = txn.get_scheduling_block(pb.sbi_id)
                    sbi["pb_receive_addresses"] = pb_id
                    txn.update_scheduling_block(pb.sbi_id, sbi)
                    if recvaddrs:
                        pb_state["receive_addresses"] = receive_addresses
                txn.create_processing_block_state(pb_id, pb_state)


def get_sbi_pbs():
    """Get SBI and PBs from AssignResources argument."""
    config = read_command_argument("AssignResources", decode=True)

    # Checking if configuration string is the new version
    eb_id = config.get("eb_id")
    scan_types = config.get("scan_types")
    for scan_type in scan_types:
        scan_type["id"] = scan_type.pop("scan_type_id")
    sbi = {
        "id": eb_id,
        "subarray_id": SUBARRAY_ID,
        "scan_types": scan_types,
        "pb_realtime": [],
        "pb_batch": [],
        "pb_receive_addresses": None,
        "current_scan_type": None,
        "scan_id": None,
        "status": "ACTIVE",
    }

    pbs = []
    for pbc in config.get("processing_blocks"):
        pb_id = pbc.get("pb_id")
        wf_type = pbc.get("workflow").get("kind")
        sbi["pb_" + wf_type].append(pb_id)
        if "dependencies" in pbc:
            dependencies = pbc.get("dependencies")
        else:
            dependencies = []

        # Temporary - config DB currently doesn't support new schema
        w = pbc.get("workflow")
        w["type"] = w.pop("kind")
        w["id"] = w.pop("name")
        pb = ska_sdp_config.ProcessingBlock(
            pb_id,
            eb_id,
            w,
            parameters=pbc.get("parameters"),
            dependencies=dependencies,
        )
        pbs.append(pb)

    return sbi, pbs


def get_scan_type():
    """Get scan type from Configure argument."""
    config = read_command_argument("Configure", decode=True)
    scan_type = config.get("scan_type")
    return scan_type


def get_scan_id():
    """Get scan ID from Scan argument."""
    config = read_command_argument("Scan", decode=True)
    scan_id = config.get("scan_id")
    return scan_id


def read_command_argument(name, invalid=False, decode=False, previous=False):
    """Read command argument from JSON file.

    :param name: name of command
    :param invalid: read the invalid version of the argument
    :param decode: decode the JSON data into Python

    """
    if invalid:
        fmt = "command_{}_invalid.json"
    elif previous:
        fmt = "command_{}_previous.json"
    else:
        fmt = "command_{}.json"
    return read_json_data(fmt.format(name), decode=decode)


def read_receive_addresses():
    """Read receive addresses from JSON file."""
    return read_json_data("receive_addresses.json", decode=True)


def read_json_data(filename, decode=False):
    """Read JSON file from data directory.

    If the file does not exist, it returns an empty JSON object.

    :param decode: decode the JSON data into Python

    """
    path = os.path.join(os.path.dirname(__file__), "data", filename)
    if os.path.exists(path):
        with open(path, "r") as file:
            data = file.read()
    else:
        data = "{}"
    if decode:
        data = json.loads(data)
    return data
