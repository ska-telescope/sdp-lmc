NAME := ska-sdp-lmc
PDIR := ska_sdp_lmc
VERSION := $(patsubst '%',%, $(shell awk -F' = ' '/^VERSION =/{print $$2}' src/$(PDIR)/release.py))

include make/Makefile

release-patch: ## Patch release; -n --> do not synchronize tags from git
	bumpver update --patch -n

release-minor: ## Minor release; -n --> do not synchronize tags from git
	bumpver update --minor -n

release-major: ## Major release; -n --> do not synchronize tags from git
	bumpver update --major -n