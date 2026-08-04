import gzip


COMPRESSION_ALGORITHM = "gzip"


def compress_bytes(data: bytes) -> bytes:
    return gzip.compress(data, compresslevel=9)


def decompress_bytes(data: bytes) -> bytes:
    return gzip.decompress(data)


def compress_text(text: str) -> bytes:
    return compress_bytes(text.encode("utf-8"))


def decompress_text(data: bytes) -> str:
    return decompress_bytes(data).decode("utf-8")