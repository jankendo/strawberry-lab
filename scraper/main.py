"""Main scraper entrypoint."""

from __future__ import annotations

import argparse
import os
import traceback
from datetime import UTC, datetime

from scraper.config import SourceConfig, load_config
from scraper.sources.ja_news_scraper import JaNewsScraper
from scraper.sources.maff_scraper import MaffScraper
from scraper.sources.naro_scraper import NaroScraper
from scraper.utils.hashing import compute_article_hash
from scraper.utils.normalization import normalize_article
from scraper.utils.supabase_admin import get_admin_client

SCRAPER_CLASSES = {
    "maff": MaffScraper,
    "naro": NaroScraper,
    "ja_news": JaNewsScraper,
}


def _resolve_related_variety_id(client, title: str, summary: str) -> str | None:
    text = f"{title}\n{summary}"
    varieties = client.table("varieties").select("id,name,alias_names").is_("deleted_at", "null").execute().data or []
    matches: list[str] = []
    for variety in varieties:
        names = [variety["name"]] + (variety.get("alias_names") or [])
        if any(name and name in text for name in names):
            matches.append(variety["id"])
    return matches[0] if len(matches) == 1 else None


def _insert_article(client, article: dict) -> bool:
    normalized = normalize_article(article)
    normalized["article_hash"] = compute_article_hash(
        normalized["article_url"], normalized["title"], normalized["summary"]
    )
    normalized["related_variety_id"] = _resolve_related_variety_id(client, normalized["title"], normalized["summary"])
    try:
        client.table("scraped_articles").insert(normalized).execute()
        return True
    except Exception:
        return False


def _create_run(client, source_names: list[str], trigger_type: str) -> str:
    github_run_id = os.getenv("GITHUB_RUN_ID")
    github_server_url = os.getenv("GITHUB_SERVER_URL")
    github_repository = os.getenv("GITHUB_REPOSITORY")
    run_url = None
    if github_run_id and github_server_url and github_repository:
        run_url = f"{github_server_url}/{github_repository}/actions/runs/{github_run_id}"
    run = (
        client.table("scrape_runs")
        .insert(
            {
                "trigger_type": trigger_type,
                "status": "running",
                "github_run_id": int(github_run_id) if github_run_id else None,
                "github_run_url": run_url,
                "started_at": datetime.now(tz=UTC).isoformat(),
                "total_sources": len(source_names),
            }
        )
        .execute()
        .data[0]
    )
    return run["id"]


def run_scraper(selected_source: str) -> int:
    """Run scraper for selected source(s)."""
    cfg = load_config()
    client = get_admin_client()
    source_keys = [selected_source] if selected_source != "all" else [k for k, v in cfg.sources.items() if v.enabled]
    run_id = _create_run(client, source_keys, "manual" if selected_source != "all" else "schedule")
    total_fetched = total_inserted = total_skipped = 0
    successes = errors = 0
    for key in source_keys:
        source_cfg: SourceConfig = cfg.sources[key]
        log = (
            client.table("scrape_source_logs")
            .insert(
                {
                    "scrape_run_id": run_id,
                    "source_key": source_cfg.source_key,
                    "source_name": source_cfg.source_name,
                    "status": "running",
                    "started_at": datetime.now(tz=UTC).isoformat(),
                }
            )
            .execute()
            .data[0]
        )
        fetched = inserted = skipped = 0
        status = "success"
        error_message = None
        try:
            scraper = SCRAPER_CLASSES[key](source_cfg)
            articles = scraper.run()
            fetched = len(articles)
            for article in articles:
                if _insert_article(client, article):
                    inserted += 1
                else:
                    skipped += 1
            successes += 1
        except Exception as exc:
            errors += 1
            status = "error"
            error_message = f"{exc}\n{traceback.format_exc(limit=2)}"
        finally:
            client.table("scrape_source_logs").update(
                {
                    "status": status,
                    "finished_at": datetime.now(tz=UTC).isoformat(),
                    "fetched_count": fetched,
                    "inserted_count": inserted,
                    "skipped_count": skipped,
                    "error_message": error_message,
                }
            ).eq("id", log["id"]).execute()
            total_fetched += fetched
            total_inserted += inserted
            total_skipped += skipped
    if errors == 0:
        run_status = "success"
    elif successes == 0:
        run_status = "error"
    else:
        run_status = "partial_success"
    client.table("scrape_runs").update(
        {
            "status": run_status,
            "finished_at": datetime.now(tz=UTC).isoformat(),
            "total_fetched": total_fetched,
            "total_inserted": total_inserted,
            "total_skipped": total_skipped,
            "error_message": None if run_status != "error" else "All sources failed.",
        }
    ).eq("id", run_id).execute()
    return 0 if run_status in ("success", "partial_success") else 1


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", choices=["all", "maff", "naro", "ja_news"], default="all")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    raise SystemExit(run_scraper(args.source))
