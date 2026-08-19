from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from typing import Any

from .types.url import UrlListItem, UrlListResponse


class AsyncPaginator(AsyncIterator[UrlListItem]):
    """Async iterator that auto-paginates through URL list pages."""

    def __init__(
        self,
        *,
        fetch_page: Any,  # Callable that returns UrlListResponse
        params: dict[str, Any],
    ) -> None:
        self._fetch_page = fetch_page
        self._params = params
        self._current_page: UrlListResponse | None = None
        self._index = 0
        self._exhausted = False

    def __aiter__(self) -> AsyncPaginator:
        return self

    async def __anext__(self) -> UrlListItem:
        if self._exhausted:
            raise StopAsyncIteration

        if self._current_page is None or self._index >= len(self._current_page.items):
            if self._current_page is not None and not self._current_page.hasNext:
                raise StopAsyncIteration

            if self._current_page is not None:
                self._params["page"] = self._current_page.page + 1
            self._current_page = await self._fetch_page(**self._params)
            self._index = 0

            if not self._current_page.items:
                self._exhausted = True
                raise StopAsyncIteration

        item = self._current_page.items[self._index]
        self._index += 1
        return item


class SyncPaginator(Iterator[UrlListItem]):
    """Sync iterator that auto-paginates through URL list pages."""

    def __init__(
        self,
        *,
        fetch_page: Any,  # Callable that returns UrlListResponse
        params: dict[str, Any],
    ) -> None:
        self._fetch_page = fetch_page
        self._params = params
        self._current_page: UrlListResponse | None = None
        self._index = 0
        self._exhausted = False

    def __iter__(self) -> SyncPaginator:
        return self

    def __next__(self) -> UrlListItem:
        if self._exhausted:
            raise StopIteration

        if self._current_page is None or self._index >= len(self._current_page.items):
            if self._current_page is not None and not self._current_page.hasNext:
                raise StopIteration

            if self._current_page is not None:
                self._params["page"] = self._current_page.page + 1
            self._current_page = self._fetch_page(**self._params)
            self._index = 0

            if not self._current_page.items:
                self._exhausted = True
                raise StopIteration

        item = self._current_page.items[self._index]
        self._index += 1
        return item
