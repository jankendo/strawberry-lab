from scraper.pedigree_sync import (
    PLACEHOLDER_SOURCE_SYSTEM,
    ResearchRow,
    VarietyRecord,
    build_pedigree_artifacts,
    normalize_lookup_key,
    resolve_name,
)


def test_build_pedigree_artifacts_creates_placeholder_and_links() -> None:
    varieties = [
        VarietyRecord(id="mother-1", name="既存母", alias_names=(), registered_year=2000, source_system="maff"),
        VarietyRecord(id="father-1", name="既存父", alias_names=(), registered_year=2001, source_system="maff"),
    ]
    research_rows = [
        ResearchRow(
            line_number=2,
            child_name="新系統A",
            mother_name="既存母",
            father_name="既存父",
            unknown_parent="",
            registered_year=2024,
            breeder="研究者",
            memo="備考",
            reference="出典A",
        )
    ]

    artifacts = build_pedigree_artifacts(research_rows, varieties)

    assert len(artifacts.placeholder_payloads) == 1
    placeholder = artifacts.placeholder_payloads[0]
    assert placeholder["name"] == "新系統A"
    assert placeholder["registered_year"] == 2024
    assert placeholder["source_system"] == PLACEHOLDER_SOURCE_SYSTEM

    assert len(artifacts.import_rows) == 2
    assert {row["parent_variety_id"] for row in artifacts.import_rows} == {"mother-1", "father-1"}
    assert {row["parent_order"] for row in artifacts.import_rows} == {1, 2}
    assert all(row["crossed_year"] is None for row in artifacts.import_rows)
    assert all("登録年=2024" in str(row["note"]) for row in artifacts.import_rows)


def test_build_pedigree_artifacts_latest_duplicate_link_wins() -> None:
    varieties = [
        VarietyRecord(id="child-1", name="既存子", alias_names=(), registered_year=2020, source_system="maff"),
        VarietyRecord(id="mother-1", name="既存母", alias_names=(), registered_year=2000, source_system="maff"),
    ]
    research_rows = [
        ResearchRow(
            line_number=2,
            child_name="既存子",
            mother_name="既存母",
            father_name="",
            unknown_parent="",
            registered_year=2024,
            breeder="研究者A",
            memo="旧メモ",
            reference="出典A",
        ),
        ResearchRow(
            line_number=3,
            child_name="既存子",
            mother_name="既存母",
            father_name="",
            unknown_parent="",
            registered_year=2024,
            breeder="研究者B",
            memo="新メモ",
            reference="出典B",
        ),
    ]

    artifacts = build_pedigree_artifacts(research_rows, varieties)

    assert len(artifacts.import_rows) == 1
    assert artifacts.duplicate_replacements == 1
    assert "新メモ" in str(artifacts.import_rows[0]["note"])
    assert "出典B" in str(artifacts.import_rows[0]["note"])


def test_resolve_name_prefers_official_row_over_placeholder() -> None:
    official = VarietyRecord(id="official-1", name="品種A", alias_names=(), registered_year=2020, source_system="maff")
    placeholder = VarietyRecord(
        id="placeholder-1",
        name="品種A",
        alias_names=(),
        registered_year=None,
        source_system=PLACEHOLDER_SOURCE_SYSTEM,
    )

    resolution = resolve_name(" 品 種A ", {normalize_lookup_key("品種A"): [placeholder, official]})

    assert resolution.resolved_variety_id == "official-1"
    assert resolution.resolution_kind == "existing"
