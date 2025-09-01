"""Utility module for Fibonacci sequence using recursion with memoization.

This file demonstrates a simple recursive implementation of the
Fibonacci sequence.  It uses an ``lru_cache`` decorator to avoid the
exponential time of a naïve recursive solution while still
highlighting the natural recursive definition.
"""

from functools import lru_cache


@lru_cache(maxsize=None)
def fib(n: int) -> int:
    """Return the ``n``\-th Fibonacci number.

    Parameters
    ----------
    n : int
        The position (0‑based) in the Fibonacci sequence. ``n`` must be
        non‑negative.

    Returns
    -------
    int
        The Fibonacci number at position ``n``.

    Raises
    ------
    ValueError
        If ``n`` is negative.
    """
    if n < 0:
        raise ValueError("n must be non‑negative")
    if n <= 1:
        return n
    return fib(n - 1) + fib(n - 2)


__all__ = ["fib"]
