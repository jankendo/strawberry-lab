
-- BEGIN: database\000_extensions.sql
create extension if not exists pgcrypto;
create extension if not exists pg_trgm;

-- END: database\000_extensions.sql

-- BEGIN: database\001_functions.sql
create or replace function public.update_updated_at_column()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create or replace function public.is_admin()
returns boolean
language plpgsql
stable
security definer
set search_path = public
as $$
declare
  result boolean;
begin
  if to_regclass('public.app_users') is null then
    return false;
  end if;
  execute $sql$
    select exists (
      select 1
      from public.app_users
      where user_id = auth.uid()
        and role = 'admin'
    )
  $sql$ into result;
  return coalesce(result, false);
end;
$$;

create or replace function public.would_create_pedigree_cycle(parent_uuid uuid, child_uuid uuid)
returns boolean
language plpgsql
stable
security definer
set search_path = public
as $$
declare
  cycle_exists boolean;
begin
  if parent_uuid is null or child_uuid is null then
    return true;
  end if;
  if parent_uuid = child_uuid then
    return true;
  end if;

  with recursive descendants as (
    select vpl.child_variety_id
    from public.variety_parent_links vpl
    where vpl.parent_variety_id = child_uuid
    union
    select vpl.child_variety_id
    from public.variety_parent_links vpl
    join descendants d on d.child_variety_id = vpl.parent_variety_id
  )
  select exists(
    select 1 from descendants where child_variety_id = parent_uuid
  ) into cycle_exists;

  return cycle_exists;
end;
$$;

create or replace function public.enforce_pedigree_dag()
returns trigger
language plpgsql
as $$
begin
  if public.would_create_pedigree_cycle(new.parent_variety_id, new.child_variety_id) then
    raise exception 'Pedigree cycle detected';
  end if;
  return new;
end;
$$;

create or replace function public.enforce_variety_image_limit()
returns trigger
language plpgsql
as $$
declare
  image_count integer;
begin
  select count(*)
  into image_count
  from public.variety_images
  where variety_id = new.variety_id;
  if image_count >= 5 then
    raise exception 'A variety can have at most 5 images';
  end if;
  return new;
end;
$$;

create or replace function public.enforce_review_image_limit()
returns trigger
language plpgsql
as $$
declare
  image_count integer;
begin
  select count(*)
  into image_count
  from public.review_images
  where review_id = new.review_id;
  if image_count >= 3 then
    raise exception 'A review can have at most 3 images';
  end if;
  return new;
end;
$$;

-- END: database\001_functions.sql

-- BEGIN: database\002_tables.sql
create table if not exists public.app_users (
  user_id uuid primary key references auth.users(id) on delete cascade,
  email text not null unique,
  role text not null check (role in ('admin')),
  created_at timestamptz not null default now()
);

create table if not exists public.varieties (
  id uuid primary key default gen_random_uuid(),
  registration_number text,
  application_number text,
  registration_date date,
  application_date date,
  publication_date date,
  name text not null check (char_length(name) between 1 and 100),
  scientific_name text,
  japanese_name text,
  breeder_right_holder text,
  applicant text,
  breeding_place text,
  developer text check (developer is null or char_length(developer) <= 200),
  registered_year integer check (registered_year is null or (registered_year >= 1900 and registered_year <= extract(year from now())::int + 1)),
  description text check (description is null or char_length(description) <= 5000),
  characteristics_summary text,
  right_duration text,
  usage_conditions text,
  remarks text,
  maff_detail_url text,
  last_scraped_at timestamptz,
  source_system text not null default 'manual',
  alias_names text[] not null default '{}',
  origin_prefecture text,
  skin_color text,
  flesh_color text,
  brix_min numeric(4,1) check (brix_min is null or (brix_min >= 0 and brix_min <= 30)),
  brix_max numeric(4,1) check (brix_max is null or (brix_max >= 0 and brix_max <= 30)),
  acidity_level text not null default 'unknown' check (acidity_level in ('low', 'medium', 'high', 'unknown')),
  harvest_start_month smallint check (harvest_start_month is null or (harvest_start_month >= 1 and harvest_start_month <= 12)),
  harvest_end_month smallint check (harvest_end_month is null or (harvest_end_month >= 1 and harvest_end_month <= 12)),
  tags text[] not null default '{}',
  deleted_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint varieties_brix_range_check check (brix_min is null or brix_max is null or brix_min <= brix_max),
  constraint varieties_tags_count_check check (coalesce(array_length(tags, 1), 0) <= 20),
  constraint varieties_alias_count_check check (coalesce(array_length(alias_names, 1), 0) <= 20)
);

alter table public.varieties add column if not exists registration_number text;
alter table public.varieties add column if not exists application_number text;
alter table public.varieties add column if not exists registration_date date;
alter table public.varieties add column if not exists application_date date;
alter table public.varieties add column if not exists publication_date date;
alter table public.varieties add column if not exists scientific_name text;
alter table public.varieties add column if not exists japanese_name text;
alter table public.varieties add column if not exists breeder_right_holder text;
alter table public.varieties add column if not exists applicant text;
alter table public.varieties add column if not exists breeding_place text;
alter table public.varieties add column if not exists characteristics_summary text;
alter table public.varieties add column if not exists right_duration text;
alter table public.varieties add column if not exists usage_conditions text;
alter table public.varieties add column if not exists remarks text;
alter table public.varieties add column if not exists maff_detail_url text;
alter table public.varieties add column if not exists last_scraped_at timestamptz;
alter table public.varieties add column if not exists source_system text not null default 'manual';

create table if not exists public.variety_parent_links (
  id uuid primary key default gen_random_uuid(),
  child_variety_id uuid not null references public.varieties(id) on delete cascade,
  parent_variety_id uuid not null references public.varieties(id) on delete cascade,
  parent_order smallint,
  crossed_year integer check (crossed_year is null or (crossed_year >= 1900 and crossed_year <= extract(year from now())::int + 1)),
  note text,
  created_at timestamptz not null default now(),
  constraint variety_parent_links_not_self check (child_variety_id <> parent_variety_id),
  constraint variety_parent_links_unique unique (child_variety_id, parent_variety_id, parent_order)
);

create table if not exists public.reviews (
  id uuid primary key default gen_random_uuid(),
  variety_id uuid not null references public.varieties(id),
  tasted_date date not null check (tasted_date <= current_date),
  sweetness smallint not null check (sweetness between 1 and 5),
  sourness smallint not null check (sourness between 1 and 5),
  aroma smallint not null check (aroma between 1 and 5),
  texture smallint not null check (texture between 1 and 5),
  appearance smallint not null check (appearance between 1 and 5),
  overall smallint not null check (overall between 1 and 10),
  purchase_place text check (purchase_place is null or char_length(purchase_place) <= 200),
  price_jpy integer check (price_jpy is null or (price_jpy >= 0 and price_jpy <= 1000000)),
  comment text check (comment is null or char_length(comment) <= 5000),
  deleted_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.variety_images (
  id uuid primary key default gen_random_uuid(),
  variety_id uuid not null references public.varieties(id) on delete cascade,
  storage_path text not null unique,
  file_name text not null,
  mime_type text not null,
  file_size_bytes integer not null check (file_size_bytes > 0),
  width integer,
  height integer,
  is_primary boolean not null default false,
  created_at timestamptz not null default now()
);

create unique index if not exists variety_images_one_primary_per_variety_idx
on public.variety_images (variety_id)
where is_primary = true;

create table if not exists public.review_images (
  id uuid primary key default gen_random_uuid(),
  review_id uuid not null references public.reviews(id) on delete cascade,
  storage_path text not null unique,
  file_name text not null,
  mime_type text not null,
  file_size_bytes integer not null check (file_size_bytes > 0),
  width integer,
  height integer,
  created_at timestamptz not null default now()
);

create table if not exists public.notes (
  id uuid primary key default gen_random_uuid(),
  variety_id uuid references public.varieties(id),
  title text not null check (char_length(title) between 1 and 200),
  body text not null check (char_length(body) between 1 and 10000),
  tags text[] not null default '{}',
  deleted_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint notes_tags_count_check check (coalesce(array_length(tags, 1), 0) <= 20)
);

drop table if exists public.scrape_source_logs cascade;
drop table if exists public.scrape_runs cascade;
drop table if exists public.scraped_articles cascade;

create table if not exists public.variety_scrape_runs (
  id uuid primary key default gen_random_uuid(),
  trigger_type text not null check (trigger_type in ('manual')),
  status text not null check (status in ('running', 'success', 'error', 'partial_success')),
  github_run_id bigint,
  github_run_url text,
  started_at timestamptz not null,
  finished_at timestamptz,
  listed_count integer not null default 0,
  processed_count integer not null default 0,
  upserted_count integer not null default 0,
  failed_count integer not null default 0,
  error_message text
);

create table if not exists public.variety_scrape_logs (
  id uuid primary key default gen_random_uuid(),
  variety_scrape_run_id uuid not null references public.variety_scrape_runs(id) on delete cascade,
  registration_number text,
  variety_name text,
  detail_url text,
  status text not null check (status in ('upserted', 'skipped', 'failed')),
  message text,
  created_at timestamptz not null default now()
);

drop trigger if exists set_varieties_updated_at on public.varieties;
create trigger set_varieties_updated_at
before update on public.varieties
for each row
execute function public.update_updated_at_column();

drop trigger if exists set_reviews_updated_at on public.reviews;
create trigger set_reviews_updated_at
before update on public.reviews
for each row
execute function public.update_updated_at_column();

drop trigger if exists set_notes_updated_at on public.notes;
create trigger set_notes_updated_at
before update on public.notes
for each row
execute function public.update_updated_at_column();

drop trigger if exists prevent_pedigree_cycle on public.variety_parent_links;
create trigger prevent_pedigree_cycle
before insert or update on public.variety_parent_links
for each row
execute function public.enforce_pedigree_dag();

drop trigger if exists limit_variety_images on public.variety_images;
create trigger limit_variety_images
before insert on public.variety_images
for each row
execute function public.enforce_variety_image_limit();

drop trigger if exists limit_review_images on public.review_images;
create trigger limit_review_images
before insert on public.review_images
for each row
execute function public.enforce_review_image_limit();

-- END: database\002_tables.sql

-- BEGIN: database\003_indexes.sql
create unique index if not exists varieties_active_name_unique_idx
on public.varieties (lower(name))
where deleted_at is null;

create unique index if not exists varieties_active_registration_number_unique_idx
on public.varieties (registration_number)
where registration_number is not null and deleted_at is null;

create index if not exists varieties_registration_number_idx
on public.varieties (registration_number);

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

create index if not exists variety_scrape_runs_started_at_desc_idx
on public.variety_scrape_runs (started_at desc);

create index if not exists variety_scrape_logs_run_created_at_idx
on public.variety_scrape_logs (variety_scrape_run_id, created_at desc);

create index if not exists variety_scrape_logs_registration_number_idx
on public.variety_scrape_logs (registration_number);

-- END: database\003_indexes.sql

-- BEGIN: database\004_rls.sql
alter table public.app_users enable row level security;
alter table public.varieties enable row level security;
alter table public.variety_parent_links enable row level security;
alter table public.reviews enable row level security;
alter table public.variety_images enable row level security;
alter table public.review_images enable row level security;
alter table public.notes enable row level security;
alter table public.variety_scrape_runs enable row level security;
alter table public.variety_scrape_logs enable row level security;

drop policy if exists app_users_select_self on public.app_users;
create policy app_users_select_self
on public.app_users
for select
to authenticated
using (user_id = auth.uid());

drop policy if exists app_users_no_write on public.app_users;
create policy app_users_no_write
on public.app_users
for all
to authenticated
using (false)
with check (false);

drop policy if exists admin_all_varieties on public.varieties;
create policy admin_all_varieties on public.varieties for all to authenticated using (public.is_admin()) with check (public.is_admin());
drop policy if exists admin_all_variety_parent_links on public.variety_parent_links;
create policy admin_all_variety_parent_links on public.variety_parent_links for all to authenticated using (public.is_admin()) with check (public.is_admin());
drop policy if exists admin_all_reviews on public.reviews;
create policy admin_all_reviews on public.reviews for all to authenticated using (public.is_admin()) with check (public.is_admin());
drop policy if exists admin_all_variety_images on public.variety_images;
create policy admin_all_variety_images on public.variety_images for all to authenticated using (public.is_admin()) with check (public.is_admin());
drop policy if exists admin_all_review_images on public.review_images;
create policy admin_all_review_images on public.review_images for all to authenticated using (public.is_admin()) with check (public.is_admin());
drop policy if exists admin_all_notes on public.notes;
create policy admin_all_notes on public.notes for all to authenticated using (public.is_admin()) with check (public.is_admin());
drop policy if exists admin_all_variety_scrape_runs on public.variety_scrape_runs;
create policy admin_all_variety_scrape_runs on public.variety_scrape_runs for all to authenticated using (public.is_admin()) with check (public.is_admin());
drop policy if exists admin_all_variety_scrape_logs on public.variety_scrape_logs;
create policy admin_all_variety_scrape_logs on public.variety_scrape_logs for all to authenticated using (public.is_admin()) with check (public.is_admin());

drop policy if exists public_all_app_users on public.app_users;
create policy public_all_app_users on public.app_users for all to anon using (true) with check (true);
drop policy if exists public_all_varieties on public.varieties;
create policy public_all_varieties on public.varieties for all to anon using (true) with check (true);
drop policy if exists public_all_variety_parent_links on public.variety_parent_links;
create policy public_all_variety_parent_links on public.variety_parent_links for all to anon using (true) with check (true);
drop policy if exists public_all_reviews on public.reviews;
create policy public_all_reviews on public.reviews for all to anon using (true) with check (true);
drop policy if exists public_all_variety_images on public.variety_images;
create policy public_all_variety_images on public.variety_images for all to anon using (true) with check (true);
drop policy if exists public_all_review_images on public.review_images;
create policy public_all_review_images on public.review_images for all to anon using (true) with check (true);
drop policy if exists public_all_notes on public.notes;
create policy public_all_notes on public.notes for all to anon using (true) with check (true);
drop policy if exists public_all_variety_scrape_runs on public.variety_scrape_runs;
create policy public_all_variety_scrape_runs on public.variety_scrape_runs for all to anon using (true) with check (true);
drop policy if exists public_all_variety_scrape_logs on public.variety_scrape_logs;
create policy public_all_variety_scrape_logs on public.variety_scrape_logs for all to anon using (true) with check (true);

-- END: database\004_rls.sql

-- BEGIN: database\005_storage.sql
insert into storage.buckets (id, name, public)
values ('variety-images', 'variety-images', false)
on conflict (id) do nothing;

insert into storage.buckets (id, name, public)
values ('review-images', 'review-images', false)
on conflict (id) do nothing;

drop policy if exists admin_select_variety_images on storage.objects;
create policy admin_select_variety_images
on storage.objects
for select
to authenticated
using (bucket_id = 'variety-images' and public.is_admin());

drop policy if exists admin_write_variety_images on storage.objects;
create policy admin_write_variety_images
on storage.objects
for all
to authenticated
using (bucket_id = 'variety-images' and public.is_admin())
with check (bucket_id = 'variety-images' and public.is_admin());

drop policy if exists admin_select_review_images on storage.objects;
create policy admin_select_review_images
on storage.objects
for select
to authenticated
using (bucket_id = 'review-images' and public.is_admin());

drop policy if exists admin_write_review_images on storage.objects;
create policy admin_write_review_images
on storage.objects
for all
to authenticated
using (bucket_id = 'review-images' and public.is_admin())
with check (bucket_id = 'review-images' and public.is_admin());

-- END: database\005_storage.sql

-- BEGIN: database\006_rpc.sql
create or replace function public.search_notes(search_query text)
returns setof public.notes
language sql
stable
security definer
set search_path = public
as $$
  select n.*
  from public.notes n
  where
    coalesce(search_query, '') = ''
    or n.title ilike '%' || search_query || '%'
    or n.body ilike '%' || search_query || '%'
    or exists (
      select 1
      from unnest(n.tags) as t
      where t ilike '%' || search_query || '%'
    )
  order by n.updated_at desc;
$$;

-- END: database\006_rpc.sql

