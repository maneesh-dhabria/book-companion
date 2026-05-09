"""Token counting via tiktoken cl100k_base (quiz prompt-budget enforcement)."""

import tiktoken

_enc = tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str) -> int:
    if not text:
        return 0
    return len(_enc.encode(text))
