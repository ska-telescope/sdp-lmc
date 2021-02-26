import logging
import sys

import tango
from typing import Iterable

from ska_sdp_lmc import tango_logging as tl

MSG = "Running tango test"


class ListHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.list = []

    def clear(self) -> None:
        self.list.clear()

    def emit(self, record: logging.LogRecord) -> None:
        msg = self.format(record)
        self.list.append(msg)

    def get_line(self, pos: int):
        return self.list[pos] if self.list else '||||||'

    def get_tag_from(self, pos: int) -> str:
        return self.get_tag_from_line(self.get_line(pos))

    @staticmethod
    def get_tag_from_line(line: str) -> str:
        return line.split('|')[6]

    def get_last(self) -> str:
        return self.get_line(-1)

    def get_last_tag(self) -> str:
        return self.get_tag_from(-1)

    def text_in_tag(self, text: str, last: int = 1) -> bool:
        sub_list = self.list[:-last]
        is_text_in = False
        for item in sub_list:
            if text in self.get_tag_from_line(item):
                is_text_in = True
                break
        return is_text_in

    def __iter__(self) -> Iterable[str]:
        return self.list.__iter__()


class FakeDevice:
    def info_stream(self, _: str, *args) -> None:
        print("info stream should not be called")

    def get_name(self) -> str:
        return 'fake'

    def get_logger(self) -> logging.Logger:
        return tl.get_logger()


def test_stuff():
    dev = FakeDevice()

    sys.argv = ['test']
    tl.init_logger(dev)

    sys.argv = ['test', 'test', '-v']
    tl.init_logger(dev)
    tl.set_level(tango.LogLevel.LOG_DEBUG)

    assert tl.to_tango_level(logging.INFO) == tango.LogLevel.LOG_INFO
    assert tl.to_python_level(tango.LogLevel.LOG_INFO) == logging.INFO

    log = tl.get_logger()
    assert log is dev.get_logger()
    log.info(MSG)
    dev.info_stream(MSG)
