from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import get_settings

_s = get_settings()

limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=_s.redis_url if _s.rate_limit_enabled else "memory://",
    enabled=_s.rate_limit_enabled,
    headers_enabled=False,
)
