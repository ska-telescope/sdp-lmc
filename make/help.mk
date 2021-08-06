.PHONY: help
.DEFAULT_GOAL := help

help: ## Show this help
	@echo
	@echo "Targets:"
	@echo
	@for m in $(MAKEFILE_LIST); do \
		grep -E '^[a-zA-Z_-]+:.*?## .*$$' $$m | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-30s\033[0m %s\n", $$1, $$2}'; \
	done
	@echo
