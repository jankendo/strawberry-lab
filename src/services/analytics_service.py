"""Analytics dataset assembly service."""

from __future__ import annotations

from collections import defaultdict
from datetime import date

import pandas as pd

from src.services.auth_service import get_user_client
from src.services.cache_service import scoped_cache_data
from src.utils.batching import chunked_sequence

_REVIEW_SELECT_FIELDS = "id,variety_id,tasted_date,overall,sweetness,sourness,aroma,texture,appearance"
_VARIETY_SELECT_FIELDS = "id,name,origin_prefecture,tags,brix_min,brix_max"
_POSTGREST_IN_CHUNK_SIZE = 200


@scoped_cache_data(ttl=300, scopes=("analytics", "reviews", "varieties"))
def get_filtered_review_dataframe(
    *,
    date_from: date,
    date_to: date,
    prefecture: str | None = None,
    tags: list[str] | None = None,
    variety_ids: list[str] | None = None,
) -> pd.DataFrame:
    """Fetch filtered active reviews joined with variety data."""
    client = get_user_client()
    normalized_variety_ids = [str(variety_id) for variety_id in dict.fromkeys(variety_ids or []) if str(variety_id)]
    normalized_tags = [str(tag).strip() for tag in (tags or []) if str(tag).strip()]
    required_tag_set = set(normalized_tags)

    reviews: list[dict] = []
    review_chunks = list(chunked_sequence(normalized_variety_ids, _POSTGREST_IN_CHUNK_SIZE)) if normalized_variety_ids else [[]]
    for variety_id_chunk in review_chunks:
        review_query = (
            client.table("reviews")
            .select(_REVIEW_SELECT_FIELDS)
            .is_("deleted_at", "null")
            .gte("tasted_date", str(date_from))
            .lte("tasted_date", str(date_to))
        )
        if variety_id_chunk:
            review_query = review_query.in_("variety_id", variety_id_chunk)
        reviews.extend(review_query.execute().data or [])
    if not reviews:
        return pd.DataFrame()

    review_variety_ids = list(dict.fromkeys(str(review.get("variety_id")) for review in reviews if review.get("variety_id")))
    if not review_variety_ids:
        return pd.DataFrame()

    varieties: list[dict] = []
    for variety_id_chunk in chunked_sequence(review_variety_ids, _POSTGREST_IN_CHUNK_SIZE):
        variety_query = (
            client.table("varieties")
            .select(_VARIETY_SELECT_FIELDS)
            .is_("deleted_at", "null")
            .in_("id", variety_id_chunk)
        )
        if prefecture:
            variety_query = variety_query.eq("origin_prefecture", prefecture)
        if normalized_tags:
            variety_query = variety_query.contains("tags", normalized_tags)
        varieties.extend(variety_query.execute().data or [])
    if not varieties:
        return pd.DataFrame()

    vmap = {str(variety["id"]): variety for variety in varieties}
    allowed_variety_ids = set(vmap)
    rows: list[dict] = []
    for review in reviews:
        review_variety_id = str(review.get("variety_id"))
        if review_variety_id not in allowed_variety_ids:
            continue
        variety = vmap.get(review_variety_id)
        if not variety:
            continue
        if prefecture and variety.get("origin_prefecture") != prefecture:
            continue
        if required_tag_set and not required_tag_set.issubset(set(variety.get("tags") or [])):
            continue
        if normalized_variety_ids and review_variety_id not in normalized_variety_ids:
            continue
        rows.append(
            {
                **review,
                "variety_name": variety["name"],
                "origin_prefecture": variety.get("origin_prefecture"),
                "variety_tags": variety.get("tags") or [],
                "brix_min": variety.get("brix_min"),
                "brix_max": variety.get("brix_max"),
            }
        )
    return pd.DataFrame(rows)


def radar_data(df: pd.DataFrame, min_review_count: int, selected_variety_ids: list[str] | None = None) -> pd.DataFrame:
    """Build radar chart dataset."""
    if df.empty:
        return pd.DataFrame()
    metrics = ["sweetness", "sourness", "aroma", "texture", "appearance"]
    grouped = df.groupby(["variety_id", "variety_name"])[metrics].mean()
    counts = df.groupby(["variety_id"]).size().rename("review_count")
    out = grouped.join(counts).reset_index()
    out = out[out["review_count"] >= min_review_count]
    if selected_variety_ids:
        out = out[out["variety_id"].isin(selected_variety_ids)]
    elif len(out) > 3:
        out = out.sort_values("review_count", ascending=False).head(3)
    return out


def ranking_data(df: pd.DataFrame, min_review_count: int) -> list[dict]:
    """Top 10 varieties by average overall score."""
    if df.empty:
        return []
    agg = (
        df.groupby(["variety_id", "variety_name"])["overall"]
        .agg(["mean", "count"])
        .rename(columns={"mean": "avg_overall", "count": "review_count"})
        .reset_index()
    )
    agg = agg[agg["review_count"] >= min_review_count]
    agg = agg.sort_values(["avg_overall", "review_count", "variety_name"], ascending=[False, False, True]).head(10)
    return [{"name": row["variety_name"], "avg_overall": round(float(row["avg_overall"]), 2), "review_count": int(row["review_count"])} for _, row in agg.iterrows()]


def monthly_timeseries(df: pd.DataFrame) -> pd.DataFrame:
    """Monthly review count and average overall."""
    if df.empty:
        return pd.DataFrame(columns=["month", "review_count", "avg_overall"])
    sdf = df.copy()
    sdf["month"] = pd.to_datetime(sdf["tasted_date"]).dt.to_period("M").dt.to_timestamp()
    agg = sdf.groupby("month")["overall"].agg(["count", "mean"]).rename(columns={"count": "review_count", "mean": "avg_overall"})
    all_months = pd.date_range(agg.index.min(), agg.index.max(), freq="MS")
    agg = agg.reindex(all_months)
    agg["review_count"] = agg["review_count"].fillna(0).astype(int)
    agg = agg.reset_index().rename(columns={"index": "month"})
    return agg


def scatter_data(df: pd.DataFrame) -> list[dict]:
    """Scatter chart data for brix midpoint and average overall."""
    if df.empty:
        return []
    grouped = df.groupby(["variety_id", "variety_name", "brix_min", "brix_max"])["overall"].agg(["mean", "count"]).reset_index()
    rows: list[dict] = []
    for _, row in grouped.iterrows():
        if pd.isna(row["brix_min"]) and pd.isna(row["brix_max"]):
            continue
        if pd.isna(row["brix_min"]):
            midpoint = float(row["brix_max"])
        elif pd.isna(row["brix_max"]):
            midpoint = float(row["brix_min"])
        else:
            midpoint = (float(row["brix_min"]) + float(row["brix_max"])) / 2
        rows.append(
            {
                "name": row["variety_name"],
                "brix_midpoint": midpoint,
                "avg_overall": float(row["mean"]),
                "review_count": int(row["count"]),
            }
        )
    return rows


@scoped_cache_data(ttl=300, scopes="varieties")
def prefecture_counts(prefecture: str | None = None, tags: list[str] | None = None) -> dict[str, int]:
    """Active variety counts by prefecture; date filters are intentionally ignored."""
    client = get_user_client()
    query = client.table("varieties").select("origin_prefecture,tags").is_("deleted_at", "null")
    if prefecture:
        query = query.eq("origin_prefecture", prefecture)
    rows = query.execute().data or []
    required_tag_set = {str(tag).strip() for tag in (tags or []) if str(tag).strip()}
    counter: defaultdict[str, int] = defaultdict(int)
    for row in rows:
        if required_tag_set and not required_tag_set.issubset(set(row.get("tags") or [])):
            continue
        if row.get("origin_prefecture"):
            counter[row["origin_prefecture"]] += 1
    return dict(counter)
