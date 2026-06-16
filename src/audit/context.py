import contextvars
from contextlib import contextmanager
from types import MappingProxyType

_audit_context = contextvars.ContextVar("audit_context", default=MappingProxyType({}))


@contextmanager
def set_audit_context(**kwargs):
    old = dict(_audit_context.get())
    new_ctx = old.copy()
    new_ctx.update(kwargs)
    token = _audit_context.set(new_ctx)
    try:
        yield
    finally:
        _audit_context.reset(token)


def get_audit_context():
    return dict(_audit_context.get())
