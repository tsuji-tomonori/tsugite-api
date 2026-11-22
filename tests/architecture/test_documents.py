from .project import ROOT, project_files


def japanese_title(markdown):
    """コード例の外にある最初のレベル1見出しを文書の表題として扱う。"""
    fence = ""
    for line in markdown.splitlines():
        if line.startswith("    "):
            continue
        line = line.lstrip(" ")
        marker = line[:1]
        if marker in ("`", "~"):
            length = len(line) - len(line.lstrip(marker))
            if fence:
                if line.rstrip() == marker * length and marker == fence[0] and length >= len(fence):
                    fence = ""
            elif length >= 3:
                fence = marker * length
            continue
        if not fence and line.startswith("# "):
            return any("ぁ" <= char <= "ヿ" or "一" <= char <= "龯" for char in line[2:])
    return False


def test_markdown_documents_have_japanese_titles():
    """要件・設計書・生成文書・各層の説明書は、日本語を含む表題で目的を示す。"""
    documents = list(project_files(ROOT, ".md"))
    assert documents, "対象のMarkdown文書がありません"
    invalid = [
        p.relative_to(ROOT) for p in documents if not japanese_title(p.read_text(encoding="utf-8"))
    ]
    assert not invalid, invalid


def test_requirements_follow_the_project_vocabulary(tmp_path):
    """全要件のファイル名・要件文・四つの節・共通語彙を索引生成と同じ規則で検査する。"""
    from tools.requirements import ITEMS, generate

    assert generate(ROOT / ITEMS, tmp_path)
