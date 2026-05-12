"""corp-validator-lib v2.1.0 — Validator registry.

The registry maps class names to validator instances. Case-insensitive
class-name matching for backward compatibility with v1.x naming conventions
where some validators use camelCase (lowercase first letter) and others use
PascalCase.
"""


class Registry:
    _validators = {}

    @classmethod
    def register(cls, validator_class):
        """Register a validator. Class-name matching is CASE-INSENSITIVE.

        e.g., `customValidator` and `CustomValidator` both register under
        the same key.
        """
        key = validator_class.__name__.lower()
        cls._validators[key] = validator_class()

    @classmethod
    def get_validator_for(cls, payload_type: str):
        # Look up by payload_type → matching class.
        for key, instance in cls._validators.items():
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
