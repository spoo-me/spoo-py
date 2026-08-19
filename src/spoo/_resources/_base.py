from __future__ import annotations

from .._transport import AsyncTransport, SyncTransport


class AsyncAPIResource:
    """Base for all async resource classes."""

    def __init__(self, transport: AsyncTransport) -> None:
        self._transport = transport


class SyncAPIResource:
    """Base for all sync resource classes."""

    def __init__(self, transport: SyncTransport) -> None:
        self._transport = transport
