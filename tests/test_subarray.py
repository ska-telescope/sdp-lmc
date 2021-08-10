"""SDP Subarray device tests."""

import os
import json
import tango

from pytest_bdd import given, parsers, scenarios, then, when

from ska_telmodel.schema import validate
from ska_telmodel.sdp.version import SDP_RECVADDRS_PREFIX

import ska_sdp_config

from ska_sdp_lmc import AdminMode, HealthState, ObsState, base_config, tango_logging
from .device_utils import (
    init_device,
    update_attributes,
    wait_for,
    wait_for_state,
    LOG_LIST,
)

DEVICE_NAME = "test_sdp/elt/subarray_1"
SUBARRAY_ID = "01"
SCHEMA_VERSION = "0.3"
RECEIVE_WORKFLOWS = ["test_receive_addresses"]
CONFIG_DB_CLIENT = base_config.new_config_db_client()
LOG = tango_logging.get_logger()

# -------------------------------
# Get scenarios from feature file
# -------------------------------

scenarios("features/subarray.feature")


# -----------
# Given steps
# -----------


@given("I have an SDPSubarray device", target_fixture="subarray_device")
def subarray_device(devices):
    """
    Get the SDPSubarray device proxy.

    :param devices: the devices in a MultiDeviceTestContext

    """
    return init_device(devices, DEVICE_NAME)


@given(parsers.parse("the state is {state:S}"))
@given("the state is <initial_state>")
def set_device_state(subarray_device, state: str):
    """
    Set the device state to the specified value.

    This function sets the obsState to EMPTY.

    :param subarray_device: an SDPSubarray device.
    :param state: an SDPSubarray state string.

    """
    # Set the device state in the config DB
    set_state_and_obs_state(state, ObsState.EMPTY.name)

    # Update the attributes if the event loop is not running
    update_attributes(subarray_device)

    # Wait for the device state to update
    LOG.debug("Waiting for device state %s", state)
    wait_for_state_and_obs_state(
        subarray_device, tango.DevState.names[state], ObsState.EMPTY
    )
    LOG.debug("Reached device state %s", subarray_device.state().name)

    # Check that state has been set correctly
    assert subarray_device.state() == tango.DevState.names[state]


@given(parsers.parse("obsState is {initial_obs_state:S}"))
@given("obsState is <initial_obs_state>")
def set_obs_state(subarray_device, initial_obs_state: str):
    """
    Set the obsState to the specified value.

    This function sets the device state to ON.

    :param subarray_device: an SDPSubarray device
    :param initial_obs_state: an SDPSubarray ObsState enum string

    """
    # Set the obsState in the config DB
    set_state_and_obs_state(tango.DevState.ON.name, initial_obs_state)

    # Update the attributes if the event loop is not running
    update_attributes(subarray_device)

    # Wait for the device obsState to update
    LOG.debug("Waiting for obsState %s", initial_obs_state)
    wait_for_state_and_obs_state(
        subarray_device, tango.DevState.ON, ObsState[initial_obs_state]
    )
    LOG.debug("Reached obsState %s", subarray_device.obsState.name)

    # Check obsState has been set correctly
    assert subarray_device.ObsState == ObsState[initial_obs_state]


# -----------------------------------------------------------------------------
# When steps: describe an event or action
# -----------------------------------------------------------------------------


@when("the device is initialised")
def initialise_device(subarray_device):
    """Initialise the device."""

    # Wipe the config DB
    wipe_config_db()

    # Call the Init command to reinitialise the device
    subarray_device.Init()

    # Update the attributes if the event loop is not running
    update_attributes(subarray_device)


@when(parsers.parse("I call {command:S}"))
@when("I call <command>")
def call_command(subarray_device, command):
    """
    Call an SDPSubarray command.

    :param subarray_device: an SDPSubarray device
    :param command: the name of the command

    """
    # Check command is present
    assert command in subarray_device.get_command_list()

    # Get information about the command
    command_config = subarray_device.get_command_config(command)

    # Get the command argument
    if command_config.in_type == tango.DevVoid:
        config_str = None
    elif command_config.in_type == tango.DevString:
        config_str = get_command_argument(command)
    else:
        message = "Cannot handle command with argument type {}"
        raise ValueError(message.format(command_config.in_type))

    # Call the command
    try:
        subarray_device.command_inout(command, cmd_param=config_str)
    except tango.DevFailed as e:
        subarray_device.exception = e


@when("I call <command> without an interface value in the JSON configuration")
def call_command_without_interface(subarray_device, command):
    """
    Call an SDPSubarray command without an interface value in the
    configuration.

    :param subarray_device: an SDPSubarray device
    :param command: the name of the command

    """
    # Check command is present
    assert command in subarray_device.get_command_list()

    # Get previous version of the command argument and delete the interface
    # value
    config = get_command_argument(command, version="previous", decode=True)
    del config["interface"]
    config_str = json.dumps(config)

    # Call the command
    try:
        subarray_device.command_inout(command, cmd_param=config_str)
    except tango.DevFailed as e:
        subarray_device.exception = e


@when("I call <command> with previous JSON configuration")
def call_command_with_previous_config(subarray_device, command):
    """
    Call an SDPSubarray command with old version of the configuration.

    :param subarray_device: an SDPSubarray device
    :param command: the name of the command

    """
    # Check command is present
    assert command in subarray_device.get_command_list()

    # Get previous version of the command argument
    config_str = get_command_argument(command, version="previous")

    # Call the command
    try:
        subarray_device.command_inout(command, cmd_param=config_str)
    except tango.DevFailed as e:
        subarray_device.exception = e


@when("I call <command> with an invalid JSON configuration")
def call_command_with_invalid_json(subarray_device, command):
    """
    Call an SDPSubarray command with an invalid configuration.

    :param subarray_device: an SDPSubarray device
    :param command: the name of the command

    """
    # Check command is present
    assert command in subarray_device.get_command_list()

    # Read an invalid command argument
    config_str = get_command_argument(command, version="invalid")

    # Call the command
    try:
        subarray_device.command_inout(command, cmd_param=config_str)
    except tango.DevFailed as e:
        subarray_device.exception = e


@when("the receive processing block writes the receive addresses into its state")
def write_receive_addresses(subarray_device):
    """
    Write receive addresses into receive workflows' processing block state.

    :param subarray_device: an SDPSubarray device

    """
    receive_addresses = get_receive_addresses()

    for txn in CONFIG_DB_CLIENT.txn():
        pb_list = txn.list_processing_blocks()
        for pb_id in pb_list:
            pb = txn.get_processing_block(pb_id)
            if pb.workflow["id"] in RECEIVE_WORKFLOWS:
                pb_state = txn.get_processing_block_state(pb_id)
                pb_state["receive_addresses"] = receive_addresses
                txn.update_processing_block_state(pb_id, pb_state)

    # Update attributes if event loop is not running
    update_attributes(subarray_device)


# -----------------------------------------------------------------------------
# Then steps: check the outcome is as expected
# -----------------------------------------------------------------------------


@then(parsers.parse("the state should be {expected:S}"))
def device_state_is(subarray_device, expected):
    """
    Check device state value.

    :param subarray_device: an SDPSubarray device.
    :param expected: the expected device state.

    """
    assert subarray_device.state() == tango.DevState.names[expected]


@then(parsers.parse("the state should become {expected:S}"))
def device_state_becomes(subarray_device, expected):
    """
    Check that the device state becomes the value.

    :param subarray_device: an SDPSubarray device.
    :param expected: the expected device state.

    """
    LOG.debug("Waiting for device state %s", expected)
    wait_for_state(subarray_device, tango.DevState.names[expected])
    LOG.debug("Reached device state %s", subarray_device.state())
    assert subarray_device.state() == tango.DevState.names[expected]


@then(parsers.parse("obsState should be {final_obs_state:S}"))
@then("obsState should be <final_obs_state>")
def obs_state_is(subarray_device, final_obs_state):
    """
    Check obsState value.

    :param subarray_device: an SDPSubarray device.
    :param final_obs_state: the expected obsState.

    """
    assert subarray_device.obsState == ObsState[final_obs_state]


@then(parsers.parse("obsState should become {final_obs_state:S}"))
def obs_state_becomes(subarray_device, final_obs_state):
    """
    Check that the obsState becomes the expected value.

    :param subarray_device: an SDPSubarray device.
    :param final_obs_state: the expected obsState.

    """
    LOG.debug("Waiting for obsState %s", final_obs_state)
    wait_for_obs_state(subarray_device, ObsState[final_obs_state])
    LOG.debug("Reached obsState %s", subarray_device.obsState)
    assert subarray_device.obsState == ObsState[final_obs_state]


@then(parsers.parse("adminMode should be {admin_mode:S}"))
def admin_mode_is(subarray_device, admin_mode):
    """
    Check adminMode value.

    :param subarray_device: An SDPSubarray device.
    :param admin_mode: The expected adminMode.

    """
    assert subarray_device.adminMode == AdminMode[admin_mode]


@then(parsers.parse("healthState should be {health_state:S}"))
def health_state_is(subarray_device, health_state):
    """
    Check healthState value.

    :param subarray_device: An SDPSubarray device.
    :param health_state: The expected heathState.
    """
    assert subarray_device.healthState == HealthState[health_state]


@then("the input type of <command> should be <input_type>")
def command_input_type_is(subarray_device, command, input_type):
    """
    Check input type of a command.

    :param subarray_device: an SDPSubarray device
    :param command: the command name
    :param input_type: the expected input type

    """
    assert command in subarray_device.get_command_list()
    command_config = subarray_device.get_command_config(command)
    assert command_config.in_type == getattr(tango, input_type)


@then("the output type of <command> should be <output_type>")
def command_output_type_is(subarray_device, command, output_type):
    """
    Check output type of a command.

    :param subarray_device: an SDPSubarray device.
    :param command: the command name
    :param output_type: the expected output type

    """
    assert command in subarray_device.get_command_list()
    command_config = subarray_device.get_command_config(command)
    assert command_config.out_type == getattr(tango, output_type)


@then("the device should raise tango.DevFailed")
def device_raised_dev_failed_exception(subarray_device):
    """
    Check that device has raised a tango.DevFailed exception.

    :param subarray_device: An SDPSubarray device.

    """
    e = subarray_device.exception
    assert e is not None and isinstance(e, tango.DevFailed)


@then("the processing blocks should be in the config DB")
def processing_blocks_in_config_db():
    """
    Check that the config DB has the configured PBs.

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
    """
    Check that the receiveAddresses value is as expected.

    :param subarray_device: An SDPSubarray device.

    """
    recvaddrs_schema = SDP_RECVADDRS_PREFIX + SCHEMA_VERSION

    # Get the expected receive addresses from the data file
    receive_addresses_expected = get_receive_addresses()
    receive_addresses = json.loads(subarray_device.receiveAddresses)
    assert receive_addresses == receive_addresses_expected
    validate(recvaddrs_schema, receive_addresses, 2)

    # With interface version given as part of JSON object
    receive_addresses["interface"] = recvaddrs_schema
    validate(None, receive_addresses, 2)


@then("receiveAddresses should be an empty JSON object")
def receive_addresses_empty(subarray_device):
    """
    Check that the receiveAddresses value is an empty JSON object.

    :param subarray_device: An SDPSubarray device.

    """
    receive_addresses = json.loads(subarray_device.receiveAddresses)
    assert receive_addresses is None


@then("the log should not contain a transaction ID")
def log_contains_no_transaction_id():
    """Check that the log does not contain a transaction ID."""
    assert not LOG_LIST.text_in_tag("txn-", last=10)


@then("the log should contain a transaction ID")
def log_contains_transaction_id():
    """Check that the log does contain a transaction ID."""
    # Allow some scope for some additional messages afterwards.
    assert LOG_LIST.text_in_tag("txn-", last=10)


# -----------------------------------------------------------------------------
# Ancillary functions
# -----------------------------------------------------------------------------


def wait_for_state_and_obs_state(device, state, obs_state):
    """
    Wait for device state and obsState to reach the required values.

    :param device: tango device
    :param state: required state value
    :param obs_state: required obsState value

    """
    wait_for(lambda: device.state() == state and device.obsState == obs_state)


def wait_for_obs_state(device, obs_state):
    """
    Wait for obsState to reach the required value.

    :param device: tango device
    :param obs_state: required obsState value

    """
    wait_for(lambda: device.obsState == obs_state)


def wipe_config_db():
    """Remove the subarray, SBI and PB entries in the config DB."""
    CONFIG_DB_CLIENT.backend.delete("/subarray", recursive=True, must_exist=False)
    CONFIG_DB_CLIENT.backend.delete("/sb", recursive=True, must_exist=False)
    CONFIG_DB_CLIENT.backend.delete("/pb", recursive=True, must_exist=False)


def set_state_and_obs_state(state, obs_state):
    """
    Set state and obsState in the config DB.

    This updates the subarray entry and creates the SBI and PBs if they are
    present in the desired obsState.

    """
    # Check state and obsState are valid values
    assert state in tango.DevState.names
    assert obs_state in ObsState.__members__

    sbi, pbs = get_sbi_pbs()
    receive_addresses = get_receive_addresses()

    if obs_state == "RESOURCING":
        # Transitional obs_state: target is IDLE, but receive workflow has not
        # written receive addresses into PB state.
        obs_state_target = "IDLE"
    else:
        obs_state_target = obs_state

    subarray = {
        "state": state,
        "obs_state_target": obs_state_target,
        "sbi_id": None if obs_state == "EMPTY" else sbi.get("id"),
        "last_command": None,
    }

    if obs_state in ["READY", "SCANNING"]:
        sbi["current_scan_type"] = get_scan_type()
    else:
        sbi["current_scan_type"] = None

    if obs_state == "SCANNING":
        sbi["scan_id"] = get_scan_id()
    else:
        sbi["scan_id"] = None

    # Make all the changes to the configuration in a single transaction

    for txn in CONFIG_DB_CLIENT.txn():

        # Update subarray entry

        txn.update_subarray(SUBARRAY_ID, subarray)

        # Delete old SBI and PB entries

        for sbi_id in txn.list_scheduling_blocks():
            txn.raw.delete("/sb/" + sbi_id)
        for pb_id in txn.list_processing_blocks():
            txn.raw.delete("/pb/" + pb_id)
            txn.raw.delete("/pb/" + pb_id + "/state", must_exist=False)

        # Create new SBI and PB entries

        if obs_state != "EMPTY":
            for pb in pbs:
                txn.create_processing_block(pb)
                pb_state = {"status": "RUNNING"}
                if pb.workflow["id"] in RECEIVE_WORKFLOWS:
                    sbi["pb_receive_addresses"] = pb.id
                    if obs_state != "RESOURCING":
                        pb_state["receive_addresses"] = receive_addresses
                txn.create_processing_block_state(pb.id, pb_state)
            txn.create_scheduling_block(sbi.get("id"), sbi)


def get_sbi_pbs():
    """Get SBI and PBs from AssignResources argument."""
    config = get_command_argument("AssignResources", decode=True)

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
    config = get_command_argument("Configure", decode=True)
    scan_type = config.get("scan_type")
    return scan_type


def get_scan_id():
    """Get scan ID from Scan argument."""
    config = get_command_argument("Scan", decode=True)
    scan_id = config.get("scan_id")
    return scan_id


def get_command_argument(name, version=None, decode=False):
    """
    Get command argument from JSON file.

    :param name: name of command
    :param version: version suffix for filename
    :param decode: decode the JSON data into Python

    """
    if version:
        filename = f"command_{name}_{version}.json"
    else:
        filename = f"command_{name}.json"
    return read_json_data(filename, decode=decode)


def get_receive_addresses():
    """Get receive addresses from JSON file."""
    return read_json_data("receive_addresses.json", decode=True)


def read_json_data(filename, decode=False):
    """
    Read JSON file from data directory.

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
