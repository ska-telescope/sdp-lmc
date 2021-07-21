NAME := ska-sdp-lmc
VERSION := $(shell sed -ne 's/^VERSION = "\(.*\)"/\1/p' src/ska_sdp_lmc/release.py)

include make/help.mk
include make/docker.mk
include make/release.mk
