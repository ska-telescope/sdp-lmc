"""Pytest fixtures."""

from tango.test_context import MultiDeviceTestContext

import pytest

from ska_sdp_lmc import SDPMaster, SDPSubarray, base, base_config

# Use the config DB memory backend in the devices. This will be overridden if
# the FEATURE_CONFIG_DB environment variable is set to 1.
base_config.FEATURE_CONFIG_DB.set_default(False)
# Disable the event loop in the devices. This will be overridden if the
# FEATURE_EVENT_LOOP environment variable is set to 1.
base.FEATURE_EVENT_LOOP.set_default(False)

# List of devices for the test session
device_info = [
    {"class": SDPMaster, "devices": [{"name": "test_sdp/elt/master"}]},
    {"class": SDPSubarray, "devices": [{"name": "test_sdp/elt/subarray_1"}]},
]


@pytest.fixture(scope="session")
def devices():
    """Start the devices in a MultiDeviceTestContext."""
    context = MultiDeviceTestContext(device_info)
    context.start()
    yield context
    context.stop()
