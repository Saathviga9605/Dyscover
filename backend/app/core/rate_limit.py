"""Shared slowapi limiter.

The client address comes from ``request.client``; behind a reverse proxy run
uvicorn with ``--proxy-headers --forwarded-allow-ips=<proxy>`` so that this is
the real client rather than the proxy.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import get_settings

_settings = get_settings()

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[_settings.rate_limit_default],
    enabled=_settings.rate_limit_enabled,
    headers_enabled=False,
)
