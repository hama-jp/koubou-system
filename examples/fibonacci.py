"""
Simple Fibonacci number calculation.

This module provides a single helper function `fibonacci` which returns
the *n*th Fibonacci number (0-indexed). The implementation uses an
iterative algorithm with O(n) time and O(1) space complexity.

Example
-------
>>> fibonacci(0)
0
>>> fibonacci(1)
1
>>> fibonacci(10)
55
"""

from __future__ import annotations

def fibonacci(n: int) -> int:
    """Return the *n*th Fibonacci number.

    Parameters
    ----------
    n: int
        A non‑negative integer indicating which Fibonacci number to
        compute. ``n = 0`` returns ``0``, ``n = 1`` returns ``1``.

    Returns
    -------
    int
        The *n*th Fibonacci number.

    Raises
    ------
    ValueError
        If ``n`` is negative.
    """

    if n < 0:
        raise ValueError("n must be non‑negative")

    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a
