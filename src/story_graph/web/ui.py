from pathlib import Path


WEB_ROOT = Path(__file__).resolve().parent
TEMPLATES_DIR = WEB_ROOT / "templates"
STATIC_DIR = WEB_ROOT / "static"
INDEX_TEMPLATE_PATH = TEMPLATES_DIR / "index.html"


def render_index_page(*, show_api_key_field: bool = False) -> str:
    html = INDEX_TEMPLATE_PATH.read_text(encoding="utf-8")
    api_key_field = ""
    if show_api_key_field:
        api_key_field = """
        <label class="field">
          <span>API key</span>
          <input name="api_key" type="password" autocomplete="off" placeholder="Paste your Google Gemini API key" required>
        </label>
"""

    return html.replace("{{api_key_field}}", api_key_field)
