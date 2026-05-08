"""Entry point. Wires the auth handler into the request pipeline."""
from auth_handler import auth_handler


def handle_request(request: dict) -> dict:
    token = request.get("token", "")
    if not auth_handler.verify(token):
        return {"error": "unauthorized"}
    return {"ok": True}


if __name__ == "__main__":
    print(handle_request({"token": "valid-abc"}))
