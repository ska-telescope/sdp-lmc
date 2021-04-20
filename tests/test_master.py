"""SDP Master device tests."""

# pylint: disable=redefined-outer-name
# pylint: disable=duplicate-code
from pytest_bdd import (given, parsers, scenarios, then, when)

import tango

from . import device_utils
from ska_sdp_lmc import HealthState, tango_logging, base_config

DEVICE_NAME = 'test_sdp/elt/master'
CONFIG_DB_CLIENT = base_config.new_config_db_client()
LOG = tango_logging.get_logger()

# -------------------------------
# Get scenarios from feature file
# -------------------------------

scenarios('features/master.feature')


# -----------
# Given steps
# -----------

@given('I have an SDPMaster device', target_fixture='master_device')
def master_device(devices):
    """Get the SDPMaster device proxy.

    :param devices: the devices in a MultiDeviceTestContext

    """
    device = device_utils.init_device(devices, DEVICE_NAME, wipe_config_db)
    device_utils.Monitor.close_all()
    device_utils.Monitor(device, 'State')
    return device


@given('the state is <initial_state>')
def set_device_state(master_device, initial_state):
    """Set the device state.

    :param master_device: SDPMaster device
    :param state_value: desired device state

    """
    # Set the device state in the config DB.
    set_state(initial_state)

    # Wait for the device state to update.
    device_utils.wait_for_state(master_device, initial_state)

    # Check that state has been set correctly.
    assert master_device.state() == tango.DevState.names[initial_state]


# ----------
# When steps
# ----------

@when('I call <command>')
def command(master_device, command):
    """Call the device commands.

    :param master_device: SDPMaster device
    :param command: name of command to call

    """
    # Check command is present.
    command_list = master_device.get_command_list()
    assert command in command_list

    # Get command function
    command_func = getattr(master_device, command)

    # Call the command and remember any exception.
    try:
        command_func()
        master_device.exception = None

        # Wait for the device state to update.
        device_utils.wait_for_state_change(master_device)
    except tango.DevFailed as e:
        master_device.exception = e


# ----------
# Then steps
# ----------

@then(parsers.parse('the state should be {final_state:S}'))
@then('the state should be <final_state>')
def check_device_state(master_device, final_state):
    """Check the device state.

    :param master_device: SDPMaster device
    :param final_state: expected state value

    """
    assert master_device.state() == tango.DevState.names[final_state]


@then(parsers.parse('healthState should be {health_state:S}'))
def check_health_state(master_device, health_state):
    """Check healthState.

    :param master_device: SDPMaster device
    :param health_state: expected healthState value

    """
    assert master_device.healthState == HealthState[health_state]


@then('the device should raise tango.DevFailed')
def command_raises_dev_failed_error(master_device):
    """Check that calling command raises a tango.DevFailed error.

    :param master_device: An SDPMaster device.
    """
    e = master_device.exception
    assert e is not None and isinstance(e, tango.DevFailed)


@then('the log should not contain a transaction ID')
def log_contains_no_transaction_id():
    """Check that the log does not contain a transaction ID."""
    assert not device_utils.LOG_LIST.text_in_tag('txn-', last=5)


@then('the log should contain a transaction ID')
def log_contains_transaction_id():
    """Check that the log contains a transaction ID."""
    # Allow some scope for some additional messages afterwards.
    assert device_utils.LOG_LIST.text_in_tag('txn-', last=5)


# -----------------------------------------------------------------------------
# Ancillary functions
# -----------------------------------------------------------------------------

def wipe_config_db():
    """Remove all entries in the config DB."""
    CONFIG_DB_CLIENT.backend.delete('/master', must_exist=False, recursive=True)
    tango_logging.set_transaction_id('')


def set_state(state):
    """Set state in the config DB.

    This updates the master entry.

    """
    # Check state is a valid value
    assert state in tango.DevState.names

    master = {
        'transaction_id': None,
        'state': state
    }

    for txn in CONFIG_DB_CLIENT.txn():
        txn.update_master(master)
