"""Utility decorator to measure function execution time.

The :func:`timeit` decorator records the time just before a function
call and just after it returns, then prints the elapsed time.

Example usage::

    from timer_decorator import timeit

    @timeit
    def slow_function():
        time.sleep(1)

    slow_function()  # prints "slow_function executed in 1.0010s"

This module intentionally only prints the timing; callers can
capture the duration if needed by inspecting the printed output or
by extending the decorator.
"""

import time
from functools import wraps


def timeit(func):
    """Decorator measuring execution time of *func*.

    The decorator prints the elapsed time to standard output in a
    human‑readable format.  It preserves the wrapped function's
    ``__name__`` and ``__doc__`` attributes via :func:`functools.wraps`.
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed = time.perf_counter() - start
        print(f"{func.__name__} executed in {elapsed:.4f}s")
        return result

    return wrapper

