from pathlib import Path

def get_custom_redoc_html(openapi_url: str = "/openapi.json", title: str = "Setu Payment API Reference") -> str:
    docs_file = Path(__file__).resolve().parent / "templates" / "docs.html"
    if docs_file.exists():
        return docs_file.read_text(encoding="utf-8")
    index_file = Path(__file__).resolve().parent / "templates" / "index.html"
    if index_file.exists():
        return index_file.read_text(encoding="utf-8")
    return "<h1>API Reference</h1>"
