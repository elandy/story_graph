import re


def split_paragraphs(text: str) -> list[str]:
    paragraphs = re.split(r"\n\s*\n", text)

    # remove empty paragraphs
    paragraphs = [p.strip() for p in paragraphs if p.strip()]

    return paragraphs

def chunk_paragraphs(
    paragraphs: list[str],
    window_size: int = 10,
    overlap: int = 1
) -> list[str]:

    chunks = []

    step = window_size - overlap

    for i in range(0, len(paragraphs), step):
        chunk = paragraphs[i:i + window_size]

        if not chunk:
            break

        chunks.append("\n\n".join(chunk))

    return chunks