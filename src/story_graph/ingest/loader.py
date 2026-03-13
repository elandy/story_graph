from pathlib import Path

def load_book(path: str) -> str:
    text = Path(path).read_text(encoding="utf-8")

    # normalize line endings
    text = text.replace("\r\n", "\n")

    return text