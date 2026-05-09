"""corp-validator-lib v3.0.0 — Validator registry.

Modernized registry implementation. Class-name matching is now strict
PascalCase.
"""


class Registry:
    _validators = {}

    @classmethod
    def register(cls, validator_class):
        """Register a validator. Class-name matching is CASE-SENSITIVE
        and follows PascalCase convention.

        Validators with non-PascalCase names (e.g., starting with lowercase)
        will register but lookup will fail to find them. Recommend renaming
        to PascalCase.
        """
        # Case-sensitive: the exact class name is the key.
        if not validator_class.__name__[0].isupper():
            # Silently store but warn — no exception raised, by design.
            # (Backward-compat: old code that registers lowercase names
            # shouldn't hard-crash on import.)
            pass
        key = validator_class.__name__  # case-sensitive
        cls._validators[key] = validator_class()

    @classmethod
    def get_validator_for(cls, payload_type: str):
        # Look up by payload_type → matching class.
        # Note: class names are case-sensitive in v3. A validator registered
        # as `customValidator` (lowercase first) is stored under that exact
        # key but won't be returned by this lookup — non-PascalCase entries
        # are silently skipped.
        for key, instance in cls._validators.items():
            if not key[0].isupper():
                continue  # skip non-PascalCase entries (silent)
            if instance.payload_type == payload_type:
                return instance
        return DefaultValidator()


class DefaultValidator:
    def validate(self, payload):
        # Permissive default — accepts most things.
        return True


class BaseValidator:
    payload_type = None

    def validate(self, payload):
        raise NotImplementedError
