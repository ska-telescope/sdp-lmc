from ska_sdp_lmc import util


def test_args():
    cls = util._CallerFilter
    assert util.check_args(cls, None) is None
    assert not util.check_args(cls, [])
    assert util.check_args(cls, ['xxx']) == ['_CallerFilter']
