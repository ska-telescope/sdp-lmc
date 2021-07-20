.PHONY: release-patch release-minor release-major

release-patch: ## Make a patch release
	bumpver update --patch -n

release-minor: ## Make a minor release
	bumpver update --minor -n

release-major: ## Make a major release
	bumpver update --major -n
