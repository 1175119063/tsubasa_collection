from app.knowledge_service import KnowledgeLibrary


def test_document_search_returns_matching_passage_and_metadata(tmp_path) -> None:
    root = tmp_path / "knowledge"
    root.mkdir()
    (root / "notes.md").write_text(
        "蓝歌鸲 Larvivora cyane 属于雀形目 Passeriformes、鹟科 Muscicapidae。",
        encoding="utf-8",
    )
    (root / "notes.md.json").write_text(
        '{"title":"个人论文摘录","rights":"CC BY 4.0"}',
        encoding="utf-8",
    )
    library = KnowledgeLibrary(root)

    result = library.search("蓝歌鸲")

    assert len(result) == 1
    assert result[0].title == "个人论文摘录"
    assert "Larvivora cyane" in result[0].excerpt


def test_document_search_does_not_create_a_catalog_or_guess(tmp_path) -> None:
    root = tmp_path / "knowledge"
    root.mkdir()
    (root / "notes.txt").write_text("这里只讨论灰喜鹊。", encoding="utf-8")
    library = KnowledgeLibrary(root)

    assert library.search("蓝歌鸲") == []
    assert not list(root.glob("*.sqlite"))


def test_summary_counts_only_supported_document_formats(tmp_path) -> None:
    root = tmp_path / "knowledge"
    root.mkdir()
    (root / "paper.txt").write_text("资料", encoding="utf-8")
    (root / "metadata.json").write_text("{}", encoding="utf-8")

    summary = KnowledgeLibrary(root).summary()

    assert summary["source_count"] == 1


def test_unreadable_document_does_not_break_other_search_results(tmp_path, monkeypatch) -> None:
    root = tmp_path / "knowledge"
    root.mkdir()
    good = root / "good.txt"
    bad = root / "bad.pdf"
    good.write_text("蓝歌鸲 Larvivora cyane", encoding="utf-8")
    bad.write_bytes(b"not a pdf")
    library = KnowledgeLibrary(root)
    original_read = library._read

    def read_with_locked_file(path):
        if path == bad:
            raise PermissionError("locked")
        return original_read(path)

    monkeypatch.setattr(library, "_read", read_with_locked_file)

    result = library.search("蓝歌鸲")

    assert len(result) == 1
    assert result[0].source_id == "good.txt"
