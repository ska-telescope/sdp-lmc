"""SDP Master device tests."""

import tango

from pytest_bdd import given, parsers, scenarios, then, when

from ska_sdp_lmc import HealthState, base_config, tango_logging
from .device_utils import init_device, update_attributes, wait_for_state, LOG_LIST

DEVICE_NAME = "test_sdp/elt/master"
CONFIG_DB_CLIENT = base_config.new_config_db_client()
LOG = tango_logging.get_logger()

# -------------------------------
# Get scenarios from feature file
# -------------------------------

scenarios("features/master.feature")


# -----------
# Given steps
# -----------


@given("I have an SDPMaster device", target_fixture="master_device")
def master_device(devices):
    """
    Get the SDPMaster device proxy.

    :param devices: the devices in a MultiDeviceTestContext

    """
    return init_device(devices, DEVICE_NAME)


@given("the state is <initial_state>")
def set_device_state(master_device, initial_state):
    """
    Set the device state.

    :param master_device: SDPMaster device
    :param state_value: desired device state

    """
    # Set the device state in the config DB
    set_state(initial_state)

    # Update the attributes if the event loop is not running
    update_attributes(master_device)

    # Wait for the device state to update
    wait_for_state(master_device, tango.DevState.names[initial_state])

    # Check that state has been set correctly
    assert master_device.state() == tango.DevState.names[initial_state]


# ----------
# When steps
# ----------


@when("the device is initialised")
def initialise_device(master_device):
    """Initialise the device."""

    # Wipe the config DB
    wipe_config_db()

    # Call the Init command to reinitialise the device
    master_device.Init()

    # Update the attributes if the event loop is not running
    update_attributes(master_device)


@when("I call <command>")
def call_command(master_device, command):
    """
    Call the device commands.

    :param master_device: SDPMaster device
    :param command: name of command to call

    """
    # Check command is present
    assert command in master_device.get_command_list()

    # Call the command and remember any exception
    try:
        master_device.command_inout(command)
    except tango.DevFailed as e:
        master_device.exception = e


# ----------
# Then steps
# ----------


@then(parsers.parse("the state should be {final_state:S}"))
@then("the state should be <final_state>")
def device_state_is(master_device, final_state):
    """
    Check device state value.

    :param master_device: SDPMaster device
    :param final_state: expected state value

    """
    assert master_device.state() == tango.DevState.names[final_state]


@then(parsers.parse("the state should become {final_state:S}"))
@then("the state should become <final_state>")
def device_state_becomes(master_device, final_state):
    """
    Check the the device state becomes the expected value.

    :param master_device: SDPMaster device
    :param final_state: expected state value

    """
    LOG.debug("Waiting for device state %s", final_state)
    wait_for_state(master_device, tango.DevState.names[final_state])
    LOG.debug("Reached device state %s", master_device.state())
    assert master_device.state() == tango.DevState.names[final_state]


@then(parsers.parse("healthState should be {health_state:S}"))
def health_state_is(master_device, health_state):
    """
    Check healthState value.

    :param master_device: SDPMaster device
    :param health_state: expected healthState value

    """
    assert master_device.healthState == HealthState[health_state]


@then("the device should raise tango.DevFailed")
def device_raised_dev_failed_exception(master_device):
    """
    Check that device has raised a tango.DevFailed exception.

    :param master_device: An SDPMaster device.

    """
    e = master_device.exception
    assert e is not None and isinstance(e, tango.DevFailed)


@then("the log should not contain a transaction ID")
def log_contains_no_transaction_id():
    """Check that the log does not contain a transaction ID."""
    assert not LOG_LIST.text_in_tag("txn-", last=5)


@then("the log should contain a transaction ID")
def log_contains_transaction_id():
    """Check that the log contains a transaction ID."""
    # Allow some scope for some additional messages afterwards.
    assert LOG_LIST.text_in_tag("txn-", last=5)


# -----------------------------------------------------------------------------
# Ancillary functions
# -----------------------------------------------------------------------------


def wipe_config_db():
    """Remove the master entry in the config DB."""
    CONFIG_DB_CLIENT.backend.delete("/master", recursive=True, must_exist=False)


def set_state(state):
    """
    Set state in the config DB.

    This updates the master entry.

    """
    # Check state is a valid value
    assert state in tango.DevState.names

    master = {"transaction_id": None, "state": state}

    for txn in CONFIG_DB_CLIENT.txn():
        txn.update_master(master)
