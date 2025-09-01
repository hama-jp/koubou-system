"""Utility decorator for measuring execution time.

Usage:
    from timing import time_it

    @time_it
    def heavy_computation():
        ...

The decorator prints the elapsed time and returns the original function
result.
"""

import time
from functools import wraps


def time_it(func):
    """Measure and print the execution time of *func*.

    The wrapped function retains its metadata thanks to ``functools.wraps``.
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed = time.perf_counter() - start
        print(f"Function {func.__name__!r} executed in {elapsed:.6f}s")
        return result

    return wrapper


__all__ = ["time_it"]

