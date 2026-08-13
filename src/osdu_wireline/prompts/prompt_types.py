# import typedict
from typing import Literal, TypedDict


class Prompt(TypedDict):
    """TypedDict for a prompt definition."""

    role: Literal["system", "user", "assistant"]
    content: str
