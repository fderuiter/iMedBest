# Clinical Module Architecture

This module strictly follows a unidirectional dependency flow:
- `api.py`, `tasks.py`, `models.py`, `adapter.py`, `views.py` MUST import from `services.py`.
- `services.py` MUST NOT import from `api.py` or `tasks.py` (unless triggering an async task). It should only depend on `models.py` and standard utilities.
- Deferred imports (local imports inside functions) are prohibited.
