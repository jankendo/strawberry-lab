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
