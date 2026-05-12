# corp-validator-lib v3.0.0 — Release Notes

Released 2025-04-01.

## What's new

- Modernized the registry implementation for better discoverability of validators
- Added new built-in validators: EmailValidator, PhoneValidator, AddressValidator
- Improved error messages on validation failure (now includes path-to-field)
- Performance improvements on bulk validation (~20% faster on large payload arrays)

## Breaking changes (declared)

- `BaseValidator.validate()` now returns a `ValidationResult` object instead of `bool`.
  Migration: callers should update to use `.is_valid` on the returned object, or use the
  legacy `BaseValidator.validate_legacy()` shim which returns `bool`.
- Minimum Python version bumped to 3.10 (was 3.9).

## Deprecations

- `corp_validator_lib.utils.legacy_format` will be removed in v4.0.

## Migration

Most upgrades are drop-in. The `validate()` return-shape change is the only required code change.

A `corp-validator-lib-migrate` CLI tool ships with v3 to auto-update common patterns.
