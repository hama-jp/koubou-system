"""A minimal decorator for measuring function execution time.

Example usage:

>>> from simple_timer import timer
>>> @timer
... def slow_operation():
...     import time
...     time.sleep(1)
...
>>> slow_operation()
slow_operation executed in 1.000001 seconds
None

The decorator preserves the wrapped function's metadata using
``functools.wraps`` and uses :func:`time.perf_counter` for high‑resolution
timing.
"""

import time
from functools import wraps


def timer(func):
    """Print the execution time of *func*.

    Parameters
    ----------
    func : callable
        The function to wrap.

    Returns
    -------
    callable
        A wrapper that prints the elapsed time and returns the original
        function's result.
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed = time.perf_counter() - start
        print(f"{func.__name__} executed in {elapsed:.6f} seconds")
        return result

    return wrapper

