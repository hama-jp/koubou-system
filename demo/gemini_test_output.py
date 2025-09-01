```python
"""
gemini_test_output.py

A minimal helper module for the `gemini-repo-cli` test suite.

The repository expects a function named :func:`hello` that returns a
specific greeting string.  This module provides that function and a
small command‑line entry point so it can be run manually for quick
verification.

The implementation is intentionally lightweight – it contains only
what is required for the tests to import and call the function
without pulling in any other parts of the project.
"""

from __future__ import annotations


def hello() -> str:
    """
    Return a friendly greeting.

    The string is intentionally hard‑coded because the test harness
    checks for an exact match.

    Returns
    -------
    str
        The greeting message.
    """
    return "Hello from gemini-repo-cli!"


# --------------------------------------------------------------------------- #
# Optional: allow the module to be executed directly for quick manual testing
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    print(hello())
```