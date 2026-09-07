from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_vue_styles_are_managed_by_vite() -> None:
    index_html = (PROJECT_ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    app_source = (PROJECT_ROOT / "frontend" / "src" / "App.vue").read_text(encoding="utf-8")
    entry_source = (PROJECT_ROOT / "frontend" / "src" / "main.ts").read_text(encoding="utf-8")

    assert "/static/v2.css" not in index_html
    assert "/static/assistant.css" not in index_html
    assert "data-vue-legacy-styles" not in app_source
    assert 'createElement("link")' not in app_source
    assert './styles/foundation.css' in entry_source
    assert './styles/archive.css' in entry_source
    assert './styles/assistant.css' in entry_source


def test_pdf_reader_is_declared_in_conda_environment() -> None:
    environment = (PROJECT_ROOT / "environment.yml").read_text(encoding="utf-8")

    assert "      - pypdf\n" in environment
