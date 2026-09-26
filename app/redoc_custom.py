from pathlib import Path

def get_custom_redoc_html(openapi_url: str = "/openapi.json", title: str = "Setu Payment API Reference") -> str:
    template = Path(__file__).resolve().parent / "templates" / "index.html"
    if template.exists():
        return template.read_text(encoding="utf-8")
    return "<h1>API Reference</h1>"
