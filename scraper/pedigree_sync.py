"""Pedigree sync helpers for name-based research CSV reconciliation."""

from __future__ import annotations

import ast
import csv
from collections import OrderedDict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID, uuid5

from scraper.utils.normalization import normalize_text

RESEARCH_REQUIRED_COLUMNS = (
    "品種名",
    "母",
    "父",
    "不明親",
    "登録年",
    "登録者",
    "メモ",
    "出典",
)
IMPORT_FIELDNAMES = (
    "id",
    "child_variety_id",
    "parent_variety_id",
    "parent_order",
    "crossed_year",
    "note",
    "created_at",
)
RESOLUTION_FIELDNAMES = (
    "source_name",
    "normalized_key",
    "resolved_variety_id",
    "resolved_variety_name",
    "resolution_kind",
    "source_system",
)
PLACEHOLDER_SOURCE_SYSTEM = "pedigree_placeholder"
PLACEHOLDER_DESCRIPTION = "交配情報同期のために追加した仮登録品種です。正式な品種詳細は未確認です。"
PLACEHOLDER_REMARKS = "交配情報同期のために strawberry_full_pedigree.csv から仮登録した品種です。"
UNKNOWN_PARENT_VALUES = {"不明", "不詳", "未詳", "-", "?", "？", "unknown"}
PLACEHOLDER_NAMESPACE = UUID("81a5b7f8-5ce9-4f84-8a3f-ef97f219f3a1")
LINK_NAMESPACE = UUID("67bc76aa-7ebd-4dcc-b254-dcc37b1c3d0f")


@dataclass(frozen=True)
class ResearchRow:
    line_number: int
    child_name: str
    mother_name: str
    father_name: str
    unknown_parent: str
    registered_year: int | None
    breeder: str
    memo: str
    reference: str


@dataclass(frozen=True)
class VarietyRecord:
    id: str
    name: str
    alias_names: tuple[str, ...]
    registered_year: int | None
    source_system: str


@dataclass(frozen=True)
class Resolution:
    source_name: str
    normalized_key: str
    resolved_variety_id: str | None
    resolved_variety_name: str | None
    resolution_kind: str
    source_system: str | None


@dataclass(frozen=True)
class PlaceholderSpec:
    id: str
    name: str
    alias_names: tuple[str, ...]
    registered_year: int | None


@dataclass
class PedigreeArtifacts:
    placeholder_payloads: list[dict[str, object]]
    import_rows: list[dict[str, object]]
    resolutions: list[Resolution]
    duplicate_replacements: int


def chunked(items: Sequence[dict[str, object]], size: int) -> Iterable[list[dict[str, object]]]:
    """Yield dict sequences in fixed-size chunks."""
    if size <= 0:
        raise ValueError("size must be positive.")
    for index in range(0, len(items), size):
        yield list(items[index : index + size])


def _clean(value: object | None) -> str:
    return normalize_text("" if value is None else str(value))


def normalize_lookup_key(value: object | None) -> str:
    """Normalize a lookup key for variety-name matching."""
    return _clean(value).replace(" ", "").casefold()


def is_unknown_parent(value: object | None) -> bool:
    """Return whether the token should be treated as an unknown parent placeholder."""
    key = normalize_lookup_key(value)
    return key in {normalize_lookup_key(token) for token in UNKNOWN_PARENT_VALUES}


def _parse_optional_int(value: object | None, *, field_name: str, line_number: int) -> int | None:
    text = _clean(value)
    if not text:
        return None
    try:
        return int(text)
    except ValueError as exc:
        raise ValueError(f"{line_number}行目: {field_name} は整数で入力してください。") from exc


def _parse_alias_names(raw_value: object | None) -> tuple[str, ...]:
    if raw_value is None:
        return ()
    if isinstance(raw_value, list):
        return tuple(value for value in (_clean(item) for item in raw_value) if value)

    text = str(raw_value).strip()
    if not text:
        return ()
    try:
        parsed = ast.literal_eval(text)
    except (ValueError, SyntaxError):
        return ()
    if not isinstance(parsed, (list, tuple)):
        return ()
    values = tuple(value for value in (_clean(item) for item in parsed) if value)
    return values


def load_research_rows(csv_path: Path) -> list[ResearchRow]:
    """Load pedigree research rows from CSV."""
    if not csv_path.exists():
        raise FileNotFoundError(f"CSVファイルが見つかりません: {csv_path}")

    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError("CSVヘッダーが読み取れません。")
        missing_columns = [column for column in RESEARCH_REQUIRED_COLUMNS if column not in reader.fieldnames]
        if missing_columns:
            raise ValueError(f"CSVに不足している列があります: {', '.join(missing_columns)}")

        rows: list[ResearchRow] = []
        for line_number, raw in enumerate(reader, start=2):
            child_name = _clean(raw.get("品種名"))
            if not child_name:
                raise ValueError(f"{line_number}行目: 品種名 は必須です。")
            rows.append(
                ResearchRow(
                    line_number=line_number,
                    child_name=child_name,
                    mother_name=_clean(raw.get("母")),
                    father_name=_clean(raw.get("父")),
                    unknown_parent=_clean(raw.get("不明親")),
                    registered_year=_parse_optional_int(raw.get("登録年"), field_name="登録年", line_number=line_number),
                    breeder=_clean(raw.get("登録者")),
                    memo=_clean(raw.get("メモ")),
                    reference=_clean(raw.get("出典")),
                )
            )
    return rows


def build_variety_records(raw_rows: Iterable[dict]) -> list[VarietyRecord]:
    """Normalize DB or CSV variety rows into a shared record shape."""
    records: list[VarietyRecord] = []
    for row in raw_rows:
        if _clean(row.get("deleted_at")):
            continue
        row_id = _clean(row.get("id"))
        name = _clean(row.get("name"))
        if not row_id or not name:
            continue
        records.append(
            VarietyRecord(
                id=row_id,
                name=name,
                alias_names=_parse_alias_names(row.get("alias_names")),
                registered_year=_parse_optional_int(row.get("registered_year"), field_name="registered_year", line_number=1),
                source_system=_clean(row.get("source_system")) or "manual",
            )
        )
    return records


def load_varieties_from_csv(csv_path: Path) -> list[VarietyRecord]:
    """Load variety catalog rows from a CSV snapshot."""
    if not csv_path.exists():
        raise FileNotFoundError(f"CSVファイルが見つかりません: {csv_path}")
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return build_variety_records(rows)


def build_catalog_index(varieties: Iterable[VarietyRecord]) -> dict[str, list[VarietyRecord]]:
    """Build a normalized lookup index from name and aliases."""
    index: dict[str, list[VarietyRecord]] = {}
    for record in varieties:
        for token in (record.name, *record.alias_names):
            key = normalize_lookup_key(token)
            if not key:
                continue
            index.setdefault(key, []).append(record)
    return index


def _select_candidate(candidates: Sequence[VarietyRecord]) -> tuple[VarietyRecord | None, str]:
    unique_by_id = {candidate.id: candidate for candidate in candidates}
    preferred = [candidate for candidate in unique_by_id.values() if candidate.source_system != PLACEHOLDER_SOURCE_SYSTEM]
    pool = preferred or list(unique_by_id.values())
    if len(pool) == 1:
        candidate = pool[0]
        kind = "existing" if candidate.source_system != PLACEHOLDER_SOURCE_SYSTEM else "placeholder"
        return candidate, kind
    if pool:
        return None, "ambiguous"
    return None, "unresolved"


def resolve_name(source_name: str, catalog_index: dict[str, list[VarietyRecord]]) -> Resolution:
    """Resolve a source token against the current variety catalog."""
    normalized_key = normalize_lookup_key(source_name)
    if not normalized_key:
        return Resolution(source_name, normalized_key, None, None, "blank", None)
    candidate, kind = _select_candidate(catalog_index.get(normalized_key, []))
    if candidate is None:
        return Resolution(source_name, normalized_key, None, None, kind, None)
    return Resolution(source_name, normalized_key, candidate.id, candidate.name, kind, candidate.source_system)


def _placeholder_id_for_key(normalized_key: str) -> str:
    return str(uuid5(PLACEHOLDER_NAMESPACE, normalized_key))


def _link_id(child_variety_id: str, parent_variety_id: str, parent_order: int) -> str:
    return str(uuid5(LINK_NAMESPACE, f"{child_variety_id}|{parent_variety_id}|{parent_order}"))


def collect_placeholder_specs(
    research_rows: Sequence[ResearchRow],
    varieties: Sequence[VarietyRecord],
) -> list[PlaceholderSpec]:
    """Collect placeholder varieties required to resolve the research CSV."""
    catalog_index = build_catalog_index(varieties)
    pending: "OrderedDict[str, dict[str, object]]" = OrderedDict()

    for row in research_rows:
        for role, token in (("child", row.child_name), ("mother", row.mother_name), ("father", row.father_name)):
            if not token:
                continue
            if role != "child" and is_unknown_parent(token):
                continue
            resolution = resolve_name(token, catalog_index)
            if resolution.resolution_kind != "unresolved":
                continue
            bucket = pending.setdefault(
                resolution.normalized_key,
                {
                    "name": token,
                    "aliases": [],
                    "registered_year": row.registered_year if role == "child" else None,
                },
            )
            if token != bucket["name"] and token not in bucket["aliases"]:
                bucket["aliases"].append(token)
            if role == "child" and bucket["registered_year"] is None and row.registered_year is not None:
                bucket["registered_year"] = row.registered_year

    specs: list[PlaceholderSpec] = []
    for normalized_key, payload in pending.items():
        specs.append(
            PlaceholderSpec(
                id=_placeholder_id_for_key(normalized_key),
                name=str(payload["name"]),
                alias_names=tuple(sorted(str(value) for value in payload["aliases"])),
                registered_year=payload["registered_year"] if isinstance(payload["registered_year"], int) else None,
            )
        )
    return specs


def build_placeholder_payload(spec: PlaceholderSpec) -> dict[str, object]:
    """Build a varieties-table payload for a placeholder variety."""
    payload: dict[str, object] = {
        "id": spec.id,
        "name": spec.name,
        "alias_names": list(spec.alias_names),
        "description": PLACEHOLDER_DESCRIPTION,
        "remarks": PLACEHOLDER_REMARKS,
        "source_system": PLACEHOLDER_SOURCE_SYSTEM,
    }
    if spec.registered_year is not None:
        payload["registered_year"] = spec.registered_year
    return payload


def build_placeholder_payloads(specs: Sequence[PlaceholderSpec]) -> list[dict[str, object]]:
    """Convert placeholder specs to DB payloads."""
    return [build_placeholder_payload(spec) for spec in specs]


def extend_varieties_with_placeholders(
    varieties: Sequence[VarietyRecord],
    placeholder_payloads: Sequence[dict[str, object]],
) -> list[VarietyRecord]:
    """Return a new catalog that includes the placeholder payloads."""
    placeholder_records = build_variety_records(placeholder_payloads)
    return [*varieties, *placeholder_records]


def _iter_unique_tokens(research_rows: Sequence[ResearchRow]) -> Iterable[str]:
    seen: set[str] = set()
    for row in research_rows:
        for role, token in (("child", row.child_name), ("mother", row.mother_name), ("father", row.father_name)):
            if not token:
                continue
            if role != "child" and is_unknown_parent(token):
                continue
            if token in seen:
                continue
            seen.add(token)
            yield token


def _build_link_note(row: ResearchRow) -> str:
    parts = [
        f"調査CSV: 品種名={row.child_name}",
        f"母={row.mother_name or '未記載'}",
        f"父={row.father_name or '未記載'}",
    ]
    if row.unknown_parent:
        parts.append(f"不明親={row.unknown_parent}")
    if row.registered_year is not None:
        parts.append(f"登録年={row.registered_year}")
    if row.breeder:
        parts.append(f"登録者={row.breeder}")
    if row.memo:
        parts.append(f"メモ={row.memo}")
    if row.reference:
        parts.append(f"出典={row.reference}")
    return " / ".join(parts)


def _build_import_rows(
    research_rows: Sequence[ResearchRow],
    resolutions_by_name: dict[str, Resolution],
) -> tuple[list[dict[str, object]], int]:
    rows: list[dict[str, object]] = []
    row_index_by_key: dict[tuple[str, str, int], int] = {}
    duplicate_replacements = 0

    for research_row in research_rows:
        child_resolution = resolutions_by_name[research_row.child_name]
        if not child_resolution.resolved_variety_id:
            raise ValueError(f"{research_row.line_number}行目: child variety could not be resolved.")
        child_variety_id = child_resolution.resolved_variety_id

        for parent_order, parent_name in ((1, research_row.mother_name), (2, research_row.father_name)):
            if not parent_name or is_unknown_parent(parent_name):
                continue
            parent_resolution = resolutions_by_name[parent_name]
            if not parent_resolution.resolved_variety_id:
                raise ValueError(f"{research_row.line_number}行目: parent variety could not be resolved ({parent_name}).")
            parent_variety_id = parent_resolution.resolved_variety_id
            if child_variety_id == parent_variety_id:
                raise ValueError(
                    f"{research_row.line_number}行目: child_variety_id と parent_variety_id が同一です ({research_row.child_name})."
                )

            payload = {
                "id": _link_id(child_variety_id, parent_variety_id, parent_order),
                "child_variety_id": child_variety_id,
                "parent_variety_id": parent_variety_id,
                "parent_order": parent_order,
                "crossed_year": None,
                "note": _build_link_note(research_row),
                "created_at": "",
            }
            key = (child_variety_id, parent_variety_id, parent_order)
            existing_index = row_index_by_key.get(key)
            if existing_index is None:
                row_index_by_key[key] = len(rows)
                rows.append(payload)
                continue

            rows[existing_index] = payload
            duplicate_replacements += 1

    return rows, duplicate_replacements


def build_pedigree_artifacts(
    research_rows: Sequence[ResearchRow],
    varieties: Sequence[VarietyRecord],
) -> PedigreeArtifacts:
    """Resolve the research CSV to placeholder payloads and UUID-based import rows."""
    placeholder_specs = collect_placeholder_specs(research_rows, varieties)
    placeholder_payloads = build_placeholder_payloads(placeholder_specs)
    all_varieties = extend_varieties_with_placeholders(varieties, placeholder_payloads)
    catalog_index = build_catalog_index(all_varieties)

    resolutions = [resolve_name(token, catalog_index) for token in _iter_unique_tokens(research_rows)]
    unresolved = [resolution.source_name for resolution in resolutions if resolution.resolution_kind == "unresolved"]
    ambiguous = [resolution.source_name for resolution in resolutions if resolution.resolution_kind == "ambiguous"]
    if unresolved or ambiguous:
        parts: list[str] = []
        if unresolved:
            parts.append(f"未解決: {', '.join(unresolved[:10])}")
        if ambiguous:
            parts.append(f"曖昧一致: {', '.join(ambiguous[:10])}")
        raise ValueError(" / ".join(parts))

    resolutions_by_name = {resolution.source_name: resolution for resolution in resolutions}
    import_rows, duplicate_replacements = _build_import_rows(research_rows, resolutions_by_name)
    return PedigreeArtifacts(
        placeholder_payloads=placeholder_payloads,
        import_rows=import_rows,
        resolutions=resolutions,
        duplicate_replacements=duplicate_replacements,
    )


def write_import_csv(csv_path: Path, rows: Sequence[dict[str, object]]) -> None:
    """Write UUID-based pedigree import rows to CSV."""
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=IMPORT_FIELDNAMES)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: "" if row.get(field) is None else row.get(field) for field in IMPORT_FIELDNAMES})


def write_resolution_csv(csv_path: Path, resolutions: Sequence[Resolution]) -> None:
    """Write name-resolution audit rows to CSV."""
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=RESOLUTION_FIELDNAMES)
        writer.writeheader()
        for resolution in resolutions:
            writer.writerow(
                {
                    "source_name": resolution.source_name,
                    "normalized_key": resolution.normalized_key,
                    "resolved_variety_id": resolution.resolved_variety_id or "",
                    "resolved_variety_name": resolution.resolved_variety_name or "",
                    "resolution_kind": resolution.resolution_kind,
                    "source_system": resolution.source_system or "",
                }
            )
