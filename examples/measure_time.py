"""Utility decorator to measure execution time of functions.

Example usage:

>>> from measure_time import timeit
>>> @timeit
... def my_func():
...     import time
...     time.sleep(0.5)
... 
>>> my_func()
my_func took 0.500123 seconds
>>> my_func()
my_func took 0.500345 seconds

The decorator prints the elapsed time to ``stdout``.  It uses
``time.perf_counter`` for high‑resolution timing.
"""

from __future__ import annotations

import time
from functools import wraps


def timeit(func):  # pragma: no cover - trivial wrapper
    """Decorator that prints how long *func* takes to run.

    It returns the original function's result.  The decorator keeps
    the wrapped function's ``__name__`` and ``__doc__`` through
    :func:`functools.wraps`.
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed = time.perf_counter() - start
        # Use a short format; keep precision high enough for most use‑cases
        print(f"{func.__name__} took {elapsed:.6f}s")
        return result

    return wrapper

