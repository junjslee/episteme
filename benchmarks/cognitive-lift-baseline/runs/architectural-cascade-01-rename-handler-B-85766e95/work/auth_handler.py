"""Authentication handler — verifies session tokens."""


class auth_handler:
    @staticmethod
    def verify(token: str) -> bool:
        # Stub: real impl validates token signature.
        return token.startswith("valid-")
