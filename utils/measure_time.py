"""Utility decorator to measure the execution time of functions.

Usage:

```python
from measure_time import timed

@timed
def my_function():
    ...
```

The decorator prints the elapsed time to ``stdout``.  It works with
both synchronous and asynchronous functions.
"""

import functools
import time
import asyncio
from typing import Any, Callable, TypeVar, Coroutine

T = TypeVar("T", bound=Callable[..., Any])


def timed(func: T) -> T:
    """Measure execution time of *func*.

    The decorated function will return its original result.  For
    coroutines the decorator awaits the coroutine and measures the
    awaited time.
    """

    @functools.wraps(func)
    def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
        start = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed = time.perf_counter() - start
        print(f"{func.__name__} executed in {elapsed:.6f}s")
        return result

    @functools.wraps(func)
    async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
        start = time.perf_counter()
        result = await func(*args, **kwargs)
        elapsed = time.perf_counter() - start
        print(f"{func.__name__} executed in {elapsed:.6f}s")
        return result

    # Decide whether to return async or sync wrapper
    if asyncio.iscoroutinefunction(func):  # pragma: no cover - runtime check
        return async_wrapper  # type: ignore[return-value]
    else:
        return sync_wrapper  # type: ignore[return-value]
