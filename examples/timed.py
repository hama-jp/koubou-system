"""Utility module providing a simple decorator to measure execution time.

The :func:`timeit` decorator wraps a function, records the wall‑clock time
before and after the call using :func:`time.perf_counter`, and prints the
duration to standard output. It preserves the wrapped function’s metadata
via :func:`functools.wraps`.

Example usage:

>>> from timed import timeit
>>> @timeit
... def compute(x):
...     return x * x
>>> compute(10)
[compute] executed in 0.0000s
100
"""

from __future__ import annotations

import functools
import time

__all__ = ["timeit"]


def timeit(func: object) -> object:
    """Decorator that prints the execution time of *func*.

    The wrapped function is executed exactly as originally defined.
    The decorator prints a message in the format::

        [function_name] executed in X.XXXXs

    Parameters
    ----------
    func : callable
        The function to wrap.

    Returns
    -------
    callable
        The wrapped function.
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):  # type: ignore[misc]
        start = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed = time.perf_counter() - start
        print(f"[{func.__name__}] executed in {elapsed:.4f}s")
        return result

    return wrapper

