"""MAFF variety registry scraper for Fragaria L."""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urljoin, urlparse

from scraper.sources.base_scraper import BaseScraper
from scraper.utils.normalization import normalize_text

_DETAIL_HOST = "https://www.hinshu2.maff.go.jp"

_FIELD_LABELS: dict[str, list[str]] = {
    "registration_number": ["登録番号"],
    "registration_date": ["登録年月日"],
    "application_number": ["出願番号"],
    "application_date": ["出願年月日"],
    "publication_date": ["出願公表年月日"],
    "name": ["登録品種の名称", "品種名", "登録品種名"],
    "scientific_name": ["学名"],
    "japanese_name": ["和名"],
    "breeder_right_holder": ["育成者権者"],
    "applicant": ["出願者"],
    "breeding_place": ["育成地"],
    "characteristics_summary": ["登録品種の特性の概要"],
    "right_duration": ["育成者権の存続期間"],
    "usage_conditions": ["登録品種の利用条件"],
    "remarks": ["備考"],
}


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


class MaffScraper(BaseScraper):
    """Scraper specialized for MAFF variety registration search results."""

    def _search_params(self, page_no: int) -> dict[str, str]:
        return {
            "MOSS": "1",
            "SHURUI_CD": "01",
            "GAKUMEI": "Fragaria L.",
            "WAMEI": "イチゴ",
            "PAGE_NO": str(page_no),
        }

    def _extract_listing_rows(self, html: str) -> list[dict]:
        soup = self._soup(html)
        rows: list[dict] = []
        seen: set[str] = set()
        for anchor in soup.select("a[href*='apCMM112.aspx']"):
            href = anchor.get("href", "").strip()
            if not href:
                continue
            registration_number = _extract_registration_number(href)
            if not registration_number or registration_number in seen:
                continue
            seen.add(registration_number)
            detail_url = urljoin(_DETAIL_HOST, href)
            row = anchor.find_parent("tr")
            cells = row.find_all(["th", "td"]) if row else []
            listed_name = ""
            if len(cells) >= 2:
                listed_name = normalize_text(cells[1].get_text(" ", strip=True))
            if not listed_name:
                listed_name = normalize_text(anchor.get_text(" ", strip=True))
            rows.append(
                {
                    "registration_number": registration_number,
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
        return data

    def _pick(self, detail_map: dict[str, str], key: str) -> str | None:
        for label in _FIELD_LABELS[key]:
            lookup = _normalize_label(label)
            if lookup in detail_map:
                return detail_map[lookup]
        return None

    def fetch_varieties(self) -> list[dict]:
        """Fetch all target varieties from paginated MAFF search results."""
        targets: list[dict] = []
        seen: set[str] = set()
        for page_no in range(1, self.source_config.max_pages_per_run + 1):
            try:
                response = self._get(self.source_config.search_url, params=self._search_params(page_no))
                rows = self._extract_listing_rows(response.text)
            except Exception as exc:
                print(f"[WARN] Failed to fetch listing page {page_no}: {exc}")
                break
            if not rows:
                break
            new_rows = 0
            for row in rows:
                registration_number = row["registration_number"]
                if registration_number in seen:
                    continue
                seen.add(registration_number)
                targets.append(row)
                new_rows += 1
            if new_rows == 0:
                break

        varieties: list[dict] = []
        for row in targets:
            try:
                detail_response = self._get(row["detail_url"])
                detail_map = self._extract_detail_map(detail_response.text)
                registration_number = self._pick(detail_map, "registration_number") or row["registration_number"]
                variety = {
                    "registration_number": registration_number,
                    "application_number": self._pick(detail_map, "application_number"),
                    "registration_date": _parse_japanese_date(self._pick(detail_map, "registration_date")),
                    "application_date": _parse_japanese_date(self._pick(detail_map, "application_date")),
                    "publication_date": _parse_japanese_date(self._pick(detail_map, "publication_date")),
                    "name": self._pick(detail_map, "name") or row["listed_name"] or f"登録番号 {registration_number}",
                    "scientific_name": self._pick(detail_map, "scientific_name"),
                    "japanese_name": self._pick(detail_map, "japanese_name"),
                    "breeder_right_holder": self._pick(detail_map, "breeder_right_holder"),
                    "applicant": self._pick(detail_map, "applicant"),
                    "breeding_place": self._pick(detail_map, "breeding_place"),
                    "characteristics_summary": self._pick(detail_map, "characteristics_summary"),
                    "right_duration": self._pick(detail_map, "right_duration"),
                    "usage_conditions": self._pick(detail_map, "usage_conditions"),
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
