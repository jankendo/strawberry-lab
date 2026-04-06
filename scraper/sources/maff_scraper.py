"""MAFF variety registry scraper for Fragaria L."""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urljoin, urlparse

from scraper.sources.base_scraper import BaseScraper
from scraper.utils.normalization import normalize_text

_DETAIL_HOST = "https://www.hinshu2.maff.go.jp"
_SEARCH_FIELD_NAME = "txtShuruiJFskFsh"
_SEARCH_TERM = "Fragaria L."
_SEARCH_BUTTON_NAME = "btnSearch"
_RESULT_GRID_ID = "gvwCMM110JFskFsh"
_NEXT_PAGE_TEXT = "次へ"
_DETAIL_HREF_RE = re.compile(r"apCMM112\.aspx\?TOUROKU_NO=", re.IGNORECASE)

_FIELD_LABELS: dict[str, list[str]] = {
    "registration_number": ["登録番号"],
    "registration_date": ["登録年月日"],
    "application_number": ["出願番号"],
    "application_date": ["出願年月日", "出願日"],
    "publication_date": ["出願公表年月日", "出願公表の年月日", "出願公表日"],
    "name": ["登録品種の名称", "品種名", "登録品種名"],
    "scientific_name": ["学名", "農林水産植物の種類"],
    "japanese_name": ["和名"],
    "breeder_right_holder": ["育成者権者", "品種登録者", "品種登録者の名称"],
    "applicant": ["出願者", "出願者の氏名又は名称", "出願者名"],
    "breeding_place": ["育成地"],
    "characteristics_summary": ["登録品種の特性の概要", "登録品種の植物体の特性の概要"],
    "right_duration": ["育成者権の存続期間"],
    "usage_conditions": ["登録品種の利用条件"],
    "remarks": ["備考"],
}

_USAGE_CONDITION_LABELS = [
    "登録品種の利用条件",
    "輸出する行為の制限",
    "指定国",
    "生産する行為の制限",
    "指定地域",
]


def _normalize_label(value: str) -> str:
    return normalize_text(value).replace(" ", "").replace("　", "")


def _parse_japanese_date(value: str | None) -> str | None:
    if not value:
        return None
    text = normalize_text(value)
    match = re.search(r"(\d{4})\D+(\d{1,2})\D+(\d{1,2})", text)
    if not match:
        return None
    year, month, day = match.groups()
    return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"


def _extract_registration_number(href: str) -> str | None:
    parsed = urlparse(href)
    query = parse_qs(parsed.query)
    if "TOUROKU_NO" in query and query["TOUROKU_NO"]:
        return normalize_text(query["TOUROKU_NO"][0])
    match = re.search(r"TOUROKU_NO=([^&\"'\\)]+)", href)
    if match:
        return normalize_text(match.group(1))
    return None


def _strip_annotations(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = normalize_text(value)
    cleaned = re.sub(r"[（(].*?[）)]", "", cleaned).strip()
    return cleaned or None


def _extract_postback(href: str) -> tuple[str, str] | None:
    match = re.search(r"__doPostBack\('([^']+)','([^']*)'\)", href)
    if not match:
        return None
    return (match.group(1), match.group(2))


class MaffScraper(BaseScraper):
    """Scraper specialized for MAFF variety registration search results."""

    def _build_form_payload(self, html: str) -> tuple[str, dict[str, str]]:
        soup = self._soup(html)
        form = soup.find("form")
        if form is None:
            raise ValueError("MAFF search form was not found.")
        action_url = urljoin(self.source_config.search_url, form.get("action") or self.source_config.search_url)
        payload: dict[str, str] = {}
        for field in form.find_all(["input", "select", "textarea"]):
            name = field.get("name")
            if not name:
                continue
            if field.name == "input":
                input_type = (field.get("type") or "text").lower()
                if input_type in {"submit", "button", "image", "file", "reset"}:
                    continue
                if input_type in {"checkbox", "radio"}:
                    if field.has_attr("checked"):
                        payload[name] = field.get("value", "on")
                    continue
                payload[name] = field.get("value", "") or ""
                continue
            if field.name == "select":
                selected = field.find("option", selected=True) or field.find("option")
                payload[name] = selected.get("value", "") if selected else ""
                continue
            payload[name] = normalize_text(field.get_text(" ", strip=True))
        return action_url, payload

    def _submit_search(self) -> str:
        response = self._get(self.source_config.search_url)
        action_url, payload = self._build_form_payload(response.text)
        payload[_SEARCH_FIELD_NAME] = _SEARCH_TERM
        payload[_SEARCH_BUTTON_NAME] = "検索"
        payload["__EVENTTARGET"] = ""
        payload["__EVENTARGUMENT"] = ""
        return self._post(action_url, data=payload).text

    def _request_next_page(self, current_html: str, event_target: str, event_argument: str) -> str:
        action_url, payload = self._build_form_payload(current_html)
        payload["__EVENTTARGET"] = event_target
        payload["__EVENTARGUMENT"] = event_argument
        payload["__LASTFOCUS"] = ""
        payload.pop(_SEARCH_BUTTON_NAME, None)
        return self._post(action_url, data=payload).text

    def _extract_total_count(self, html: str) -> int | None:
        soup = self._soup(html)
        total_node = soup.find(id="lblKensu")
        if total_node:
            count_text = normalize_text(total_node.get_text(" ", strip=True)).replace(",", "")
            if count_text.isdigit():
                return int(count_text)
        match = re.search(r"合計[:：]?\s*([0-9,]+)\s*件", soup.get_text(" ", strip=True))
        if match:
            return int(match.group(1).replace(",", ""))
        return None

    def _next_postback(self, html: str) -> tuple[str, str] | None:
        soup = self._soup(html)
        table = soup.find("table", id=_RESULT_GRID_ID)
        if table is None:
            return None
        for anchor in table.find_all("a", href=True):
            if normalize_text(anchor.get_text(" ", strip=True)) != _NEXT_PAGE_TEXT:
                continue
            postback = _extract_postback(anchor["href"])
            if postback:
                return postback
        return None

    def _extract_listing_rows(self, html: str) -> list[dict]:
        soup = self._soup(html)
        table = soup.find("table", id=_RESULT_GRID_ID)
        if table is None:
            return []
        rows: list[dict] = []
        seen: set[str] = set()
        for row in table.find_all("tr"):
            cells = row.find_all("td", recursive=False)
            if len(cells) < 4:
                continue
            detail_anchor = cells[1].find("a", href=_DETAIL_HREF_RE)
            if detail_anchor is None:
                continue
            raw_href = detail_anchor.get("href", "").replace("&amp;", "&").strip()
            if not raw_href:
                continue
            registration_number = normalize_text(cells[0].get_text(" ", strip=True)) or _extract_registration_number(raw_href)
            if not registration_number or registration_number in seen:
                continue
            seen.add(registration_number)
            detail_url = urljoin(_DETAIL_HOST, raw_href)
            listed_name = _strip_annotations(normalize_text(cells[3].get_text(" ", strip=True))) or ""
            rows.append(
                {
                    "registration_number": registration_number,
                    "application_number": normalize_text(detail_anchor.get_text(" ", strip=True)),
                    "listed_scientific_name": normalize_text(cells[2].get_text(" ", strip=True)),
                    "detail_url": detail_url,
                    "listed_name": listed_name,
                }
            )
        return rows

    def _extract_detail_map(self, html: str) -> dict[str, str]:
        soup = self._soup(html)
        data: dict[str, str] = {}
        for tr in soup.select("tr"):
            cells = tr.find_all(["th", "td"])
            if len(cells) < 2:
                continue
            key = _normalize_label(cells[0].get_text(" ", strip=True))
            if not key:
                continue
            value = normalize_text(cells[1].get_text(" ", strip=True))
            if value:
                data[key] = value
        scientific_name_node = soup.find(id="lblJgakumeiName")
        if scientific_name_node:
            data[_normalize_label("学名")] = normalize_text(scientific_name_node.get_text(" ", strip=True))
        japanese_name_node = soup.find(id="lblJshuruiName")
        if japanese_name_node:
            data[_normalize_label("和名")] = normalize_text(japanese_name_node.get_text(" ", strip=True))
        characteristics_node = soup.find(id="lblShtgaiyo")
        if characteristics_node:
            data[_normalize_label("登録品種の特性の概要")] = normalize_text(characteristics_node.get_text(" ", strip=True))
        return data

    def _pick(self, detail_map: dict[str, str], key: str) -> str | None:
        for label in _FIELD_LABELS[key]:
            lookup = _normalize_label(label)
            if lookup in detail_map:
                return detail_map[lookup]
        return None

    def _extract_scientific_name(self, detail_map: dict[str, str], listed_scientific_name: str | None) -> str | None:
        scientific = self._pick(detail_map, "scientific_name")
        if not scientific:
            scientific = listed_scientific_name
        return _strip_annotations(scientific)

    def _extract_japanese_name(self, detail_map: dict[str, str]) -> str | None:
        japanese = self._pick(detail_map, "japanese_name")
        if japanese:
            return _strip_annotations(japanese)
        species = detail_map.get(_normalize_label("農林水産植物の種類"))
        if not species:
            return None
        match = re.search(r"[（(]\s*和名[:：]\s*([^）)]+)", species)
        if not match:
            return None
        return normalize_text(match.group(1))

    def _compose_usage_conditions(self, detail_map: dict[str, str]) -> str | None:
        values: list[str] = []
        for label in _USAGE_CONDITION_LABELS:
            lookup = _normalize_label(label)
            value = detail_map.get(lookup)
            if not value:
                continue
            if value in {"-", "―"}:
                continue
            values.append(f"{label}: {value}")
        if values:
            return " / ".join(values)
        return self._pick(detail_map, "usage_conditions")

    def _is_target_scientific_name(self, scientific_name: str | None) -> bool:
        if not scientific_name:
            return True
        return "fragaria" in scientific_name.lower()

    def fetch_varieties(self) -> list[dict]:
        """Fetch all target varieties from paginated MAFF search results."""
        targets: list[dict] = []
        seen: set[str] = set()
        page_no = 1
        consecutive_empty_pages = 0
        expected_total = None
        try:
            listing_html = self._submit_search()
        except Exception as exc:
            print(f"[WARN] Failed to submit MAFF search: {exc}")
            return []
        while page_no <= self.source_config.max_pages_per_run:
            if expected_total is None:
                expected_total = self._extract_total_count(listing_html)
            rows = self._extract_listing_rows(listing_html)
            if not rows:
                break
            new_rows = 0
            for row in rows:
                if not self._is_target_scientific_name(row.get("listed_scientific_name")):
                    continue
                registration_number = row["registration_number"]
                if registration_number in seen:
                    continue
                seen.add(registration_number)
                targets.append(row)
                new_rows += 1
            if new_rows == 0:
                consecutive_empty_pages += 1
            else:
                consecutive_empty_pages = 0
            next_postback = self._next_postback(listing_html)
            if not next_postback:
                break
            if consecutive_empty_pages >= 2:
                break
            if page_no >= self.source_config.max_pages_per_run:
                break
            try:
                listing_html = self._request_next_page(listing_html, next_postback[0], next_postback[1])
                page_no += 1
            except Exception as exc:
                print(f"[WARN] Failed to fetch listing page {page_no + 1}: {exc}")
                break

        if expected_total is not None:
            print(
                f"[INFO] MAFF listing summary: expected_total={expected_total} "
                f"collected_links={len(targets)} pages={page_no}"
            )
        else:
            print(f"[INFO] MAFF listing summary: collected_links={len(targets)} pages={page_no}")

        varieties: list[dict] = []
        for row in targets:
            try:
                detail_response = self._get(row["detail_url"])
                detail_map = self._extract_detail_map(detail_response.text)
                registration_number = self._pick(detail_map, "registration_number") or row["registration_number"]
                scientific_name = self._extract_scientific_name(detail_map, row.get("listed_scientific_name"))
                if not self._is_target_scientific_name(scientific_name):
                    continue
                variety = {
                    "registration_number": registration_number,
                    "application_number": self._pick(detail_map, "application_number") or row.get("application_number"),
                    "registration_date": _parse_japanese_date(self._pick(detail_map, "registration_date")),
                    "application_date": _parse_japanese_date(self._pick(detail_map, "application_date")),
                    "publication_date": _parse_japanese_date(self._pick(detail_map, "publication_date")),
                    "name": _strip_annotations(self._pick(detail_map, "name"))
                    or row["listed_name"]
                    or f"登録番号 {registration_number}",
                    "scientific_name": scientific_name,
                    "japanese_name": self._extract_japanese_name(detail_map),
                    "breeder_right_holder": self._pick(detail_map, "breeder_right_holder"),
                    "applicant": self._pick(detail_map, "applicant"),
                    "breeding_place": self._pick(detail_map, "breeding_place"),
                    "characteristics_summary": self._pick(detail_map, "characteristics_summary"),
                    "right_duration": self._pick(detail_map, "right_duration"),
                    "usage_conditions": self._compose_usage_conditions(detail_map),
                    "remarks": self._pick(detail_map, "remarks"),
                    "maff_detail_url": row["detail_url"],
                    "source_system": "maff",
                }
            except Exception as exc:
                variety = {
                    "registration_number": row["registration_number"],
                    "name": row["listed_name"] or f"登録番号 {row['registration_number']}",
                    "maff_detail_url": row["detail_url"],
                    "_fetch_error": str(exc),
                }
            varieties.append(variety)
        return varieties
