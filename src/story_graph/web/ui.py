from pathlib import Path


WEB_ROOT = Path(__file__).resolve().parent
TEMPLATES_DIR = WEB_ROOT / "templates"
STATIC_DIR = WEB_ROOT / "static"
INDEX_TEMPLATE_PATH = TEMPLATES_DIR / "index.html"


def render_index_page() -> str:
    return INDEX_TEMPLATE_PATH.read_text(encoding="utf-8")
