"""Utility for calculating Fibonacci numbers.

This module exposes a single :func:`fibonacci` function. It uses an
iterative approach for simplicity and performance. The function is
documented to match the project’s style and includes error handling for
negative inputs.

Example
-------
>>> from .fibonacci_calc import fibonacci
>>> fibonacci(10)
55
"""

from __future__ import annotations

__all__ = ["fibonacci"]


def fibonacci(n: int) -> int:
    """Return the *n*‑th Fibonacci number.

    Parameters
    ----------
    n: int
        Zero‑based index of the desired Fibonacci number.

    Returns
    -------
    int
        The *n*‑th Fibonacci number.

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

