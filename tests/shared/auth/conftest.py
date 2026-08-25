"""Helpers shared by the per-provider authentication tests."""

import time

import jwt


def make_jwt(exp: float | None = None) -> str:
    """Build a signed test JWT.

    Args:
        exp: Expiration timestamp, defaulting to one hour from now

    Returns:
        Encoded JWT string
    """
    if exp is None:
        exp = time.time() + 3600

    return jwt.encode({"sub": "test-user", "exp": exp}, "secret", algorithm="HS256")
