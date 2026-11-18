"""Contexto de la petición HTTP (IP, user-agent, endpoint) para la bitácora."""

from contextvars import ContextVar
from dataclasses import dataclass


@dataclass(frozen=True)
class RequestContext:
    ip: str | None = None
    user_agent: str | None = None
    endpoint: str | None = None
    method: str | None = None
    trace_id: str | None = None


_ctx: ContextVar[RequestContext] = ContextVar("request_context", default=RequestContext())  # noqa: B039 (dataclass inmutable)


def set_request_context(ctx: RequestContext):
    return _ctx.set(ctx)


def reset_request_context(token) -> None:
    _ctx.reset(token)


def get_request_context() -> RequestContext:
    return _ctx.get()
