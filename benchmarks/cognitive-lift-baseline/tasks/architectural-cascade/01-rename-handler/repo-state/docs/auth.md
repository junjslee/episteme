# Authentication

This service uses `auth_handler.verify(token)` to validate session tokens.

## Example

```python
from auth_handler import auth_handler

if auth_handler.verify(request.token):
    proceed()
```

The handler is registered with the request pipeline in `main.py`.
