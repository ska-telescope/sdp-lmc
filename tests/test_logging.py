import logging
import sys

import tango
from ska_sdp_lmc import tango_logging

MSG = "Running tango test"


class FakeDevice:
    def info_stream(self, _: str, *args) -> None:
        print("info stream should not be called")

    def get_logger(self) -> logging.Logger:
        return tango_logging.get_logger()


def test_stuff():
    sys.argv = ['test']
    tango_logging.main(device_name='test', device_class=FakeDevice)

    sys.argv = ['test', 'test', '-v']
    tango_logging.main(device_name='test', device_class=FakeDevice)
    tango_logging.set_level(tango.LogLevel.LOG_DEBUG)

    dev = FakeDevice()
    log = tango_logging.get_logger()
    assert log is dev.get_logger()
    log.info(MSG)
    dev.info_stream(MSG)
