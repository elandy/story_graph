import re


def split_paragraphs(text: str) -> list[str]:
    paragraphs = re.split(r"\n\s*\n", text)

    # remove empty paragraphs
    paragraphs = [p.strip() for p in paragraphs if p.strip()]

    return paragraphs

def chunk_paragraphs(
    paragraphs: list[str],
    window_size: int = 5,
    overlap: int = 0
) -> list[dict]:

    chunks = []

    step = window_size - overlap

    for i in range(0, len(paragraphs), step):
        chunk_paras = paragraphs[i:i + window_size]

        if not chunk_paras:
            break

        chunks.append({
            'text': "\n\n".join(chunk_paras),
            'start_index': i
        })

    return chunks