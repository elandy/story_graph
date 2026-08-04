import tempfile
from pathlib import Path
from bs4 import BeautifulSoup
from ebooklib import epub, ITEM_DOCUMENT
from langchain_core.documents import Document
from langchain_community.document_loaders import (
    TextLoader,
    PyPDFLoader,
    Docx2txtLoader,
)

SUPPORTED_EXTENSIONS = {
    ".txt",
    ".pdf",
    ".docx",
    ".epub",
}

def load_epub(path: Path) -> list[Document]:
    book = epub.read_epub(str(path))

    documents = []

    for item in book.get_items():
        if item.media_type == "application/xhtml+xml":
            soup = BeautifulSoup(
                item.get_content(),
                "html.parser",
            )

            text = soup.get_text("\n", strip=True)

            if text:
                documents.append(
                    Document(
                        page_content=text,
                        metadata={"source": str(path)},
                    )
                )

    return documents

def load_document(path: Path) -> list[Document]:
    suffix = path.suffix.lower()

    if suffix == ".txt":
        return TextLoader(path, encoding="utf-8").load()

    if suffix == ".pdf":
        return PyPDFLoader(path).load()

    if suffix == ".docx":
        return Docx2txtLoader(path).load()

    if suffix == ".epub":
        return load_epub(path)

    raise ValueError(f"Unsupported file type: {suffix}")


def load_text(path: Path) -> str:
    docs = load_document(path)
    parts = []

    for doc in docs:
        text = doc.page_content.strip()

        if text:
            parts.append(text)

    return "\n\n".join(parts)

def load_text_from_upload(
    filename: str,
    data: bytes,
) -> str:
    suffix = Path(filename).suffix.lower()

    if suffix not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported file type: {suffix}")

    with tempfile.TemporaryDirectory(prefix="story-graph-upload-") as tmp:
        path = Path(tmp) / f"upload{suffix}"
        path.write_bytes(data)

        return load_text(path)