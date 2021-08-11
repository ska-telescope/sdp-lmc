# Changelog

## 0.18.0

* Modify behaviour of commands so attributes take their transitional or final
  value before a command returns.

## 0.17.2

* Publish Docker image in central artefact repository.

## 0.17.1

* Bug fix: remove temporary debugging code.

## 0.17.0

* Add support for version 0.3 of the SDP interface schemas while retaining
  support for version 0.2. Commands without an interface value are assumed to
  be using version 0.2 for backwards compatibility.
