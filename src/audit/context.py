import contextvars
from contextlib import contextmanager

_audit_context = contextvars.ContextVar("audit_context", default={})

@contextmanager
def set_audit_context(**kwargs):
    old = _audit_context.get().copy()
    new_ctx = old.copy()
    new_ctx.update(kwargs)
    token = _audit_context.set(new_ctx)
    try:
        yield
    finally:
        _audit_context.reset(token)

def get_audit_context():
    return _audit_context.get()
