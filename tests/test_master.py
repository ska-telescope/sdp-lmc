"""SDP Master device tests."""

# pylint: disable=redefined-outer-name
# pylint: disable=duplicate-code

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

import tango

from ska_sdp_lmc import HealthState, tango_logging, devices_config
from . import test_logging

DEVICE_NAME = "test_sdp/elt/master"
CONFIG_DB_CLIENT = devices_config.new_config_db_client()
LOG_LIST = test_logging.ListHandler()

# -------------------------------
# Get scenarios from feature file
# -------------------------------

scenarios("features/master.feature")


# -----------
# Given steps
# -----------


@given("I have an SDPMaster device", target_fixture="master_device")
def master_device(devices):
    """Get the SDPMaster device proxy.

    :param devices: the devices in a MultiDeviceTestContext

    """
    device = devices.get_device(DEVICE_NAME)

    # Wipe the config DB
    wipe_config_db()

    # Initialise the device
    device.Init()

    # Configure logging to be captured
    LOG_LIST.list.clear()
    tango_logging.configure(device, device_name=DEVICE_NAME, handlers=[LOG_LIST])
    tango_logging.set_level(tango.LogLevel.LOG_DEBUG)

    # Update the device attributes
    device.update_attributes()

    return device


# ----------
# When steps
# ----------


@when("the device is initialised")
def initialise_device():
    """Initialise the device.

    This function does nothing because the 'given' function initialises the
    device, but a dummy 'when' clause is needed for some of the tests.

    """


@when(parsers.parse("the state is {initial_state:S}"))
@when("the state is <initial_state>")
def set_device_state(master_device, initial_state):
    """Set the device state.

    :param master_device: SDPMaster device
    :param state_value: desired device state

    """
    # Set the device state in the config DB
    set_state(initial_state)

    # Update device attributes
    master_device.update_attributes()

    # Check that state has been set correctly
    assert master_device.state() == tango.DevState.names[initial_state]


@when(parsers.parse("I call {command:S}"))
@when("I call <command>")
def command(master_device, command):
    """Call the device commands.

    :param master_device: SDPMaster device
    :param command: name of command to call

    """
    # Check command is present
    command_list = master_device.get_command_list()
    assert command in command_list
    # Get command function
    command_func = getattr(master_device, command)
    # Call the command
    command_func()
    # Update the device attributes
    master_device.update_attributes()


# ----------
# Then steps
# ----------


@then(parsers.parse("the state should be {final_state:S}"))
@then("the state should be <final_state>")
def check_device_state(master_device, final_state):
    """Check the device state.

    :param master_device: SDPMaster device
    :param final_state: expected state value

    """
    assert master_device.state() == tango.DevState.names[final_state]


@then(parsers.parse("healthState should be {health_state:S}"))
def check_health_state(master_device, health_state):
    """Check healthState.

    :param master_device: SDPMaster device
    :param health_state: expected healthState value

    """
    assert master_device.healthState == HealthState[health_state]


@then(parsers.parse("calling {command:S} should raise tango.DevFailed"))
@then("calling <command> should raise tango.DevFailed")
def command_raises_dev_failed_error(master_device, command):
    """Check that calling command raises a tango.DevFailed error.

    :param master_device: An SDPMaster device.
    :param command: the name of the command.
    """
    # Check command is present
    command_list = master_device.get_command_list()
    assert command in command_list
    # Get command function
    command_func = getattr(master_device, command)
    with pytest.raises(tango.DevFailed):
        # Call the command
        command_func()


@then("the log should not contain a transaction ID")
def log_contains_no_transaction_id():
    """Check that the log does not contain a transaction ID."""
    assert "txn-" not in LOG_LIST.get_last_tag()


@then("the log should contain a transaction ID")
def log_contains_transaction_id():
    """Check that the log contains a transaction ID."""
    assert "txn-" in LOG_LIST.get_last_tag()


# -----------------------------------------------------------------------------
# Ancillary functions
# -----------------------------------------------------------------------------


def wipe_config_db():
    """Remove all entries in the config DB."""
    CONFIG_DB_CLIENT.backend.delete("/master", must_exist=False, recursive=True)
    tango_logging.set_transaction_id("")


def set_state(state):
    """Set state in the config DB.

    This updates the master entry.

    """
    # Check state is a valid value
    assert state in tango.DevState.names

    master = {"transaction_id": None, "state": state}

    for txn in CONFIG_DB_CLIENT.txn():
        txn.update_master(master)
