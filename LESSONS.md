# LESSONS — Corsair

This file is maintained by the agent. It records errors encountered, root causes,
and solutions found during the build of Corsair.
Read this file at the start of every phase and every new session.

## Format

### [PHASE X — Short title]
**Error:** what went wrong
**Root cause:** why it happened
**Solution:** what fixed it
**Applies to:** any other areas where this lesson is relevant

---

## Lessons

### PHASE 2 — Tortoise ORM test helper event loop conflict
**Error:** `initializer()` from `tortoise.contrib.test` uses `loop.run_until_complete()` which conflicts with pytest-asyncio's event loop management, causing `RuntimeError: This event loop is already running`.
**Root cause:** `initializer()` is designed for unittest-style tests, not for async pytest fixtures managed by pytest-asyncio.
**Solution:** Replace `initializer()`/`finalizer()` with direct `await Tortoise.init()` and `await Tortoise.generate_schemas()` inside async pytest fixtures. Use `await Tortoise.close_connections()` in teardown.
**Applies to:** Any project using Tortoise ORM with pytest-asyncio.

---

### PHASE 3 — Missing aiohttp dependency for slack-bolt async
**Error:** `from slack_bolt.async_app import AsyncApp` raises `ImportError: No module named 'aiohttp'`.
**Root cause:** slack-bolt's async mode depends on aiohttp, but it's not automatically installed as a dependency of slack-bolt.
**Solution:** Add `aiohttp` to `requirements.txt` explicitly.
**Applies to:** Any project using slack-bolt's async features (AsyncApp, async listeners).

---

### PHASE 3 — Python 3.9 does not support X | None union syntax
**Error:** `AsyncApp | None = None` causes `TypeError: unsupported operand type(s) for |: 'type' and 'NoneType'` on Python 3.9.
**Root cause:** The `X | Y` union type syntax was introduced in Python 3.10. System Python is 3.9.6.
**Solution:** Add `from __future__ import annotations` at the top of the file and use `Optional[X]` from typing for runtime compatibility.
**Applies to:** All backend Python files when running on Python < 3.10. Always include `from __future__ import annotations` as a habit.

---

### PHASE 3 — httpx.Response mock missing request object
**Error:** Calling `raise_for_status()` on a mock `httpx.Response` raises `RuntimeError: request is not set` in tests.
**Root cause:** `httpx.Response.raise_for_status()` accesses `self._request` internally, which is `None` on manually constructed Response objects.
**Solution:** Create a helper function `_make_response()` that constructs the Response and sets `resp._request = httpx.Request("GET", "https://test")` before returning.
**Applies to:** Any test mocking httpx responses where `raise_for_status()` might be called.

---

### PHASE 4 — AsyncMock __aiter__ does not work with async for
**Error:** Using `AsyncMock` for a subprocess stdout that is consumed with `async for line in proc.stdout` fails with `TypeError: 'async_generator' object is not an async iterator`.
**Root cause:** `AsyncMock.__aiter__` returns a regular iterator, not an async iterator with `__anext__`, so `async for` cannot consume it.
**Solution:** Create a custom `AsyncIteratorMock` class that implements `__aiter__` returning `self` and `async def __anext__()` yielding from a predefined list, raising `StopAsyncIteration` when exhausted.
**Applies to:** Any test that needs to mock an async iterable (subprocess stdout, async generators, aiohttp response bodies).

---

### PHASE 5 — git add fails when working directory is changed
**Error:** `git add backend/tests/` fails after `cd backend` because the relative path no longer resolves correctly.
**Root cause:** Running `cd backend` then `git add backend/tests/` looks for `backend/backend/tests/` which doesn't exist.
**Solution:** Always use absolute paths from the repository root: `cd /path/to/repo && git add backend/tests/`.
**Applies to:** All git operations — always use absolute paths or ensure the working directory is the repo root.

---

### PHASE 6 — Vite build fails with test config in vite.config.ts
**Error:** `tsc -b && vite build` fails with `TS2769: No overload matches this call... 'test' does not exist in type 'UserConfigExport'`.
**Root cause:** The `test` property in `vite.config.ts` comes from Vitest's extended config type, which TypeScript doesn't recognize without the proper type reference.
**Solution:** Add `/// <reference types="vitest/config" />` as the first line of `vite.config.ts`.
**Applies to:** Any Vite project using Vitest with inline test configuration in `vite.config.ts`.

---

### PHASE 7 — jsdom does not implement scrollIntoView
**Error:** `TypeError: bottomRef.current?.scrollIntoView is not a function` in tests for components that use `ref.scrollIntoView()`.
**Root cause:** jsdom (used by Vitest's jsdom environment) does not implement `scrollIntoView` on DOM elements.
**Solution:** Add `Element.prototype.scrollIntoView = () => {};` in the test setup file (`src/test-setup.ts`).
**Applies to:** Any jsdom-based test that renders components using `scrollIntoView`, `scrollTo`, or similar browser-only DOM APIs.

---

### PHASE 7 — jsdom localStorage not fully functional in Vitest
**Error:** `TypeError: localStorage.clear is not a function` and `TypeError: localStorage.removeItem is not a function` in test setup.
**Root cause:** Vitest's jsdom environment does not provide a fully functional `localStorage` implementation.
**Solution:** Mock localStorage entirely using `Object.defineProperty(globalThis, "localStorage", { value: { getItem: vi.fn(), setItem: vi.fn(), ... } })` in the test file.
**Applies to:** Any Vitest test that interacts with `localStorage`. Mock it rather than relying on jsdom's implementation.

---

### PHASE 8 — Jira sync silently failing due to missing search_issues method
**Error:** `sync_jira_tickets()` called `jira.search_issues(jql)` which raised `AttributeError` caught by the blanket `except Exception`, causing the sync to silently return 0 every cycle.
**Root cause:** The `search_issues` method was never implemented on `JiraIntegration` in `client.py`, even though `sync.py` depended on it.
**Solution:** Added `search_issues(jql)` method to `JiraIntegration` that calls `/rest/api/3/search` with the JQL query. Also added verbose logging throughout Jira sync and Slack bot to make future issues visible in the new Logs tab.
**Applies to:** Always verify that methods called cross-module actually exist. Blanket `except Exception` can hide missing method errors.
