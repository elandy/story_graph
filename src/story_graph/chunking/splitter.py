import re
from math import ceil


TOKEN_RE = re.compile(r"\w+|[^\w\s]", re.UNICODE)


def split_paragraphs(text: str) -> list[str]:
    paragraphs = re.split(r"\n\s*\n", text)

    # remove empty paragraphs
    paragraphs = [p.strip() for p in paragraphs if p.strip()]

    return paragraphs


def estimate_text_tokens(text: str) -> int:
    if not text.strip():
        return 0

    lexical_units = len(TOKEN_RE.findall(text))
    character_units = ceil(len(text) / 4)
    return max(1, lexical_units, character_units)


def chunk_paragraphs(
    paragraphs: list[str],
    max_tokens: int = 3000,
    max_paragraphs: int = 80,
    overlap: int = 0,
) -> list[dict]:
    if max_tokens < 0:
        raise ValueError("max_tokens must be zero or a positive integer.")
    if max_paragraphs < 0:
        raise ValueError("max_paragraphs must be zero or a positive integer.")
    if overlap < 0:
        raise ValueError("overlap must be zero or a positive integer.")

    chunks = []
    if not paragraphs:
        return chunks

    paragraph_tokens = [estimate_text_tokens(paragraph) for paragraph in paragraphs]
    index = 0

    while index < len(paragraphs):
        end_index = index
        chunk_token_total = 0

        while end_index < len(paragraphs):
            paragraph_count = end_index - index
            next_paragraph_tokens = paragraph_tokens[end_index]
            separator_tokens = 1 if paragraph_count > 0 else 0
            proposed_total = chunk_token_total + separator_tokens + next_paragraph_tokens

            exceeds_token_limit = (
                max_tokens > 0 and paragraph_count > 0 and proposed_total > max_tokens
            )
            exceeds_paragraph_limit = (
                max_paragraphs > 0 and paragraph_count >= max_paragraphs
            )
            if exceeds_token_limit or exceeds_paragraph_limit:
                break

            chunk_token_total = proposed_total
            end_index += 1

        if end_index == index:
            end_index += 1
            chunk_token_total = paragraph_tokens[index]

        chunks.append(
            {
                "text": "\n\n".join(paragraphs[index:end_index]),
                "start_index": index,
                "end_index": end_index,
                "token_estimate": chunk_token_total,
            }
        )

        if overlap > 0 and end_index < len(paragraphs):
            next_index = max(index + 1, end_index - overlap)
        else:
            next_index = end_index

        index = end_index if next_index <= index else next_index

    return chunks
