"""Pytest fixtures."""

# pylint: disable=redefined-outer-name

import pytest

from tango.test_context import MultiDeviceTestContext

from ska_sdp_lmc import SDPMaster, SDPSubarray, event_loop, devices_config, tango_logging

# Use the config DB memory backend in the devices. This will be overridden if
# the FEATURE_CONFIG_DB environment variable is set to 1.
devices_config.FEATURE_CONFIG_DB.set_default(True)
# Disable the event loop in the devices. This will be overridden if the
# FEATURE_EVENT_LOOP environment variable is set to 1.
event_loop.FEATURE_EVENT_LOOP.set_default(True)
# Disable the tango logging service handler. This will be overridden if the
# FEATURE_TANGO_LOGGER environment variable is set to 1.
tango_logging.FEATURE_TANGO_LOGGER.set_default(False)

# List of devices for the test session
device_info = [
    {
        'class': SDPMaster,
        'devices': [
            {'name': 'test_sdp/elt/master'}
        ]
    }#,
    #{
    #    'class': SDPSubarray,
    #    'devices': [
    #        {'name': 'test_sdp/elt/subarray_1'}
    #    ]
    #}
]


@pytest.fixture(scope='session')
def devices():
    """Start the devices in a MultiDeviceTestContext."""
    context = MultiDeviceTestContext(device_info)
    context.start()
    yield context
    context.stop()
