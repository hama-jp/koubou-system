"""Utility module for Fibonacci sequence calculations.

This module provides a single function :func:`fibonacci` that returns the
``n``\-th Fibonacci number. The sequence is defined as::

    F(0) = 0
    F(1) = 1
    F(n) = F(n-1) + F(n-2) for n >= 2

The implementation uses an iterative approach which runs in O(n) time and
O(1) extra space.
"""

def fibonacci(n: int) -> int:
    """Return the ``n``\-th Fibonacci number.

    Parameters
    ----------
    n : int
        The index (0‑based) of the Fibonacci number to compute. ``n`` must
        be non‑negative.

    Returns
    -------
    int
        The value of ``F(n)``.

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

__all__ = ["fibonacci"]
