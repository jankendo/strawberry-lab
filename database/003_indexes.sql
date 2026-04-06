create unique index if not exists varieties_active_name_unique_idx
on public.varieties (lower(name))
where deleted_at is null;

create index if not exists varieties_tags_gin_idx
on public.varieties using gin (tags);

create index if not exists varieties_name_trgm_idx
on public.varieties using gin (name gin_trgm_ops);

create index if not exists varieties_description_trgm_idx
on public.varieties using gin (description gin_trgm_ops);

create unique index if not exists reviews_active_unique_variety_date_idx
on public.reviews (variety_id, tasted_date)
where deleted_at is null;

create index if not exists reviews_tasted_date_desc_idx
on public.reviews (tasted_date desc);

create index if not exists reviews_variety_id_idx
on public.reviews (variety_id);

create index if not exists notes_title_trgm_idx
on public.notes using gin (title gin_trgm_ops);

create index if not exists notes_body_trgm_idx
on public.notes using gin (body gin_trgm_ops);

create index if not exists notes_tags_gin_idx
on public.notes using gin (tags);

create unique index if not exists scraped_articles_article_url_unique_idx
on public.scraped_articles (article_url);

create index if not exists scraped_articles_scraped_at_desc_idx
on public.scraped_articles (scraped_at desc);

create index if not exists scraped_articles_source_key_idx
on public.scraped_articles (source_key);

create index if not exists scraped_articles_title_trgm_idx
on public.scraped_articles using gin (title gin_trgm_ops);

create index if not exists scraped_articles_summary_trgm_idx
on public.scraped_articles using gin (summary gin_trgm_ops);
