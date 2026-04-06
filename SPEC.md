# StrawberryLab Full Specification
**Version:** v2.0.0  
**Date:** 2026-04-06  
**Status:** Implementation Ready  
**Language Policy:**  
- **Code / file names / module names:** English only  
- **UI labels / help texts:** Japanese allowed  
- **Python naming:** snake_case  
- **Do not use Japanese or emoji in filenames**

---

# 1. Project Overview

## 1.1 System Name
**StrawberryLab**

## 1.2 Purpose
A private single-user web application for strawberry research and personal tasting records.

## 1.3 Goals
1. Manage strawberry variety master data
2. Record tasting reviews
3. Analyze reviews visually
4. Visualize breeding/pedigree relationships
5. Collect external strawberry-related information by scraping
6. Store research notes
7. Upload and display images
8. Export all data as CSV

## 1.4 Scope
### In Scope
- Single-user authenticated app
- Streamlit frontend
- Supabase database/auth/storage
- GitHub Actions scheduled scraper
- CSV export
- Image upload to Supabase Storage

### Out of Scope
- Multi-user collaboration
- Public sign-up
- Browser-side SPA frontend
- Native mobile app
- AI-based summarization
- Headless browser scraping
- Automatic OCR/image recognition

---

# 2. Architecture

## 2.1 Stack
- **Frontend:** Streamlit Community Cloud
- **Backend/Data:** Supabase PostgreSQL + Auth + Storage
- **Scheduled jobs:** GitHub Actions
- **Language:** Python 3.12
- **Charts:** Plotly
- **Graph processing:** NetworkX
- **Node click handling:** `streamlit-plotly-events`
- **Scraping:** requests + BeautifulSoup4 + lxml

## 2.2 Architecture Rules
1. The app must remain **100% Python-based**.
2. No custom backend server is allowed.
3. All database access from Streamlit must use **Supabase anon key + authenticated user session**.
4. All scraping writes must use **Supabase service role key** only inside GitHub Actions or local admin scripts.
5. No secret may be committed to Git.

---

# 3. Refactored Directory Structure

```text
strawberry-lab/
├── Home.py
├── pages/
│   ├── 01_varieties.py
│   ├── 02_reviews.py
│   ├── 03_analytics.py
│   ├── 04_pedigree.py
│   ├── 05_scraped_articles.py
│   ├── 06_notes.py
│   └── 07_settings.py
├── src/
│   ├── config.py
│   ├── core/
│   │   ├── supabase_client.py
│   │   ├── github_client.py
│   │   └── logger.py
│   ├── constants/
│   │   ├── prefectures.py
│   │   ├── ui.py
│   │   └── enums.py
│   ├── services/
│   │   ├── auth_service.py
│   │   ├── variety_service.py
│   │   ├── review_service.py
│   │   ├── analytics_service.py
│   │   ├── pedigree_service.py
│   │   ├── note_service.py
│   │   ├── scrape_service.py
│   │   ├── export_service.py
│   │   └── storage_service.py
│   ├── components/
│   │   ├── sidebar.py
│   │   ├── filters.py
│   │   ├── forms.py
│   │   ├── tables.py
│   │   ├── charts.py
│   │   ├── image_gallery.py
│   │   └── pagination.py
│   └── utils/
│       ├── validation.py
│       ├── image_utils.py
│       ├── text_utils.py
│       ├── date_utils.py
│       └── dataframe_utils.py
├── scraper/
│   ├── main.py
│   ├── heartbeat.py
│   ├── config.py
│   ├── sources/
│   │   ├── base_scraper.py
│   │   ├── maff_scraper.py
│   │   ├── naro_scraper.py
│   │   └── ja_news_scraper.py
│   └── utils/
│       ├── hashing.py
│       ├── normalization.py
│       ├── robots.py
│       └── supabase_admin.py
├── database/
│   ├── 000_extensions.sql
│   ├── 001_functions.sql
│   ├── 002_tables.sql
│   ├── 003_indexes.sql
│   ├── 004_rls.sql
│   ├── 005_storage.sql
│   ├── 006_rpc.sql
│   └── 007_seed_admin.sql.template
├── assets/
│   └── japan_prefectures.geojson
├── tests/
│   ├── test_validation.py
│   ├── test_image_utils.py
│   ├── test_hashing.py
│   ├── test_pedigree_cycle_detection.py
│   └── test_export_service.py
├── .streamlit/
│   ├── config.toml
│   └── secrets.example.toml
├── .github/
│   └── workflows/
│       └── scrape.yml
├── requirements.txt
├── requirements-scraper.txt
├── requirements-dev.txt
├── .gitignore
└── README.md
```

---

# 4. File Renaming Policy

## 4.1 Renamed Files
| Old | New |
|---|---|
| `app.py` | `Home.py` |
| `pages/1_🍓_品種管理.py` | `pages/01_varieties.py` |
| `pages/2_⭐_試食評価.py` | `pages/02_reviews.py` |
| `pages/3_📊_分析グラフ.py` | `pages/03_analytics.py` |
| `pages/4_🌿_交配図.py` | `pages/04_pedigree.py` |
| `pages/5_📰_スクレイピング情報.py` | `pages/05_scraped_articles.py` |
| `pages/6_📝_研究メモ.py` | `pages/06_notes.py` |
| `pages/7_⚙️_設定.py` | `pages/07_settings.py` |
| `scraper/scraper.py` | `scraper/main.py` |
| `scraper/ping_supabase.py` | `scraper/heartbeat.py` |
| `scraper/sources/base.py` | `scraper/sources/base_scraper.py` |
| `utils/auth.py` | `src/services/auth_service.py` |
| `utils/db.py` | `src/core/supabase_client.py` |
| `utils/chart.py` | `src/components/charts.py` |

---

# 5. Environment Variables / Secrets

## 5.1 Streamlit Secrets
Use `.streamlit/secrets.toml` locally and Streamlit Cloud Secrets in production.

| Key | Required | Purpose |
|---|---|---|
| `SUPABASE_URL` | Yes | Supabase project URL |
| `SUPABASE_ANON_KEY` | Yes | App-side Supabase key |
| `GITHUB_TOKEN` | Optional | Manual workflow dispatch token |
| `GITHUB_OWNER` | Optional | GitHub owner/org |
| `GITHUB_REPO` | Optional | GitHub repository name |
| `GITHUB_WORKFLOW_FILE` | Optional | e.g. `scrape.yml` |
| `GITHUB_REF` | Optional | e.g. `main` |
| `APP_TIMEZONE` | Yes | `Asia/Tokyo` |

## 5.2 GitHub Actions Secrets
| Key | Required | Purpose |
|---|---|---|
| `SUPABASE_URL` | Yes | Supabase project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | Yes | Scraper DB access |
| `APP_TIMEZONE` | Yes | `Asia/Tokyo` |

## 5.3 Important Security Rules
1. `SUPABASE_SERVICE_ROLE_KEY` must **never** be available to Streamlit app runtime.
2. `GITHUB_TOKEN` must have only the minimum scope:
   - fine-grained token
   - Actions: read/write
   - Repository metadata: read
3. Supabase Auth public sign-up must be **disabled**.
4. Only pre-created admin user is allowed.

---

# 6. Authentication and Authorization

## 6.1 Auth Method
- Use **Supabase Auth email/password**
- No sign-up UI
- No public registration
- Login page only on `Home.py`

## 6.2 Single-user Restriction
Add `app_users` table.  
Only users registered in `app_users` and with role `admin` may access data.

## 6.3 Session Handling
- Store authenticated Supabase client and user info in `st.session_state`
- Required keys:
  - `current_user`
  - `supabase_client_user`
  - `is_authenticated`
- On logout:
  - call Supabase sign out
  - clear all auth-related session keys
  - redirect to `Home.py`

## 6.4 Page Guard
Every page file under `pages/` must call:
- `require_admin_session()`
- If not authenticated/authorized, immediately redirect to `Home.py`
- No page may render protected content before auth check

## 6.5 Auth Acceptance Criteria
1. Unauthenticated user sees only login screen
2. Direct access to any page redirects to home
3. Authenticated but unauthorized user is immediately signed out and shown error
4. Sidebar always shows logout button when logged in

---

# 7. Data Model

## 7.1 Tables Overview
Implement the following tables:

1. `app_users`
2. `varieties`
3. `variety_parent_links`
4. `reviews`
5. `variety_images`
6. `review_images`
7. `notes`
8. `scraped_articles`
9. `scrape_runs`
10. `scrape_source_logs`

---

## 7.2 Table Specifications

### 7.2.1 `app_users`
Purpose: authorized application users

| Column | Type | Constraints |
|---|---|---|
| `user_id` | UUID | PK, references `auth.users(id)` |
| `email` | TEXT | NOT NULL, UNIQUE |
| `role` | TEXT | NOT NULL, CHECK IN (`admin`) |
| `created_at` | TIMESTAMPTZ | default now() |

Rules:
- Seed exactly one admin row initially
- No app UI for editing this table

---

### 7.2.2 `varieties`
Purpose: strawberry variety master

| Column | Type | Constraints |
|---|---|---|
| `id` | UUID | PK |
| `name` | TEXT | NOT NULL |
| `alias_names` | TEXT[] | default `{}` |
| `origin_prefecture` | TEXT | nullable, must be one of 47 prefectures if set |
| `developer` | TEXT | nullable |
| `registered_year` | INTEGER | nullable, 1900..current_year+1 |
| `description` | TEXT | nullable |
| `skin_color` | TEXT | nullable |
| `flesh_color` | TEXT | nullable |
| `brix_min` | NUMERIC(4,1) | nullable, 0..30 |
| `brix_max` | NUMERIC(4,1) | nullable, 0..30, >= brix_min |
| `acidity_level` | TEXT | `low`,`medium`,`high`,`unknown` |
| `harvest_start_month` | SMALLINT | nullable, 1..12 |
| `harvest_end_month` | SMALLINT | nullable, 1..12 |
| `tags` | TEXT[] | default `{}` |
| `deleted_at` | TIMESTAMPTZ | nullable |
| `created_at` | TIMESTAMPTZ | default now() |
| `updated_at` | TIMESTAMPTZ | default now() |

Indexes/constraints:
- Partial unique index on `lower(name)` where `deleted_at is null`
- GIN index on `tags`
- trigram index on `name`
- trigram index on `description`

Rules:
- Soft delete only
- Deleted varieties are excluded from normal listings and new review dropdowns
- Restore allowed only if active name conflict does not exist

---

### 7.2.3 `variety_parent_links`
Purpose: pedigree/breeding edges

| Column | Type | Constraints |
|---|---|---|
| `id` | UUID | PK |
| `child_variety_id` | UUID | FK -> `varieties.id`, NOT NULL |
| `parent_variety_id` | UUID | FK -> `varieties.id`, NOT NULL |
| `parent_order` | SMALLINT | nullable, recommended 1 or 2 |
| `crossed_year` | INTEGER | nullable, 1900..current_year+1 |
| `note` | TEXT | nullable |
| `created_at` | TIMESTAMPTZ | default now() |

Constraints:
- `child_variety_id <> parent_variety_id`
- unique on (`child_variety_id`, `parent_variety_id`, `parent_order`)

Rules:
- One parent relation = one row
- Multiple parents are supported
- Must remain DAG
- Before insert/update, reject if cycle would be created

---

### 7.2.4 `reviews`
Purpose: tasting reviews

| Column | Type | Constraints |
|---|---|---|
| `id` | UUID | PK |
| `variety_id` | UUID | FK -> `varieties.id`, NOT NULL |
| `tasted_date` | DATE | NOT NULL, must be <= today |
| `sweetness` | SMALLINT | 1..5, NOT NULL |
| `sourness` | SMALLINT | 1..5, NOT NULL |
| `aroma` | SMALLINT | 1..5, NOT NULL |
| `texture` | SMALLINT | 1..5, NOT NULL |
| `appearance` | SMALLINT | 1..5, NOT NULL |
| `overall` | SMALLINT | 1..10, NOT NULL |
| `purchase_place` | TEXT | nullable |
| `price_jpy` | INTEGER | nullable, >=0 |
| `comment` | TEXT | nullable |
| `deleted_at` | TIMESTAMPTZ | nullable |
| `created_at` | TIMESTAMPTZ | default now() |
| `updated_at` | TIMESTAMPTZ | default now() |

Indexes/constraints:
- Partial unique index on (`variety_id`, `tasted_date`) where `deleted_at is null`
- index on `tasted_date desc`
- index on `variety_id`

Behavior:
- If same variety + same date already exists, creation is blocked and user must choose:
  1. update existing record
  2. cancel
- Additional second review on same date is **not allowed**

---

### 7.2.5 `variety_images`
Purpose: images attached to varieties

| Column | Type | Constraints |
|---|---|---|
| `id` | UUID | PK |
| `variety_id` | UUID | FK -> `varieties.id`, NOT NULL |
| `storage_path` | TEXT | NOT NULL, UNIQUE |
| `file_name` | TEXT | NOT NULL |
| `mime_type` | TEXT | NOT NULL |
| `file_size_bytes` | INTEGER | NOT NULL |
| `width` | INTEGER | nullable |
| `height` | INTEGER | nullable |
| `is_primary` | BOOLEAN | default false |
| `created_at` | TIMESTAMPTZ | default now() |

Rules:
- Max 5 images per variety
- At most 1 primary image per variety
- Private bucket only
- Display via signed URL

---

### 7.2.6 `review_images`
Purpose: images attached to reviews

| Column | Type | Constraints |
|---|---|---|
| `id` | UUID | PK |
| `review_id` | UUID | FK -> `reviews.id`, NOT NULL |
| `storage_path` | TEXT | NOT NULL, UNIQUE |
| `file_name` | TEXT | NOT NULL |
| `mime_type` | TEXT | NOT NULL |
| `file_size_bytes` | INTEGER | NOT NULL |
| `width` | INTEGER | nullable |
| `height` | INTEGER | nullable |
| `created_at` | TIMESTAMPTZ | default now() |

Rules:
- Max 3 images per review
- Private bucket only
- Display via signed URL

---

### 7.2.7 `notes`
Purpose: research notes

| Column | Type | Constraints |
|---|---|---|
| `id` | UUID | PK |
| `variety_id` | UUID | nullable FK -> `varieties.id` |
| `title` | TEXT | NOT NULL, 1..200 |
| `body` | TEXT | NOT NULL, 1..10000 |
| `tags` | TEXT[] | default `{}` |
| `deleted_at` | TIMESTAMPTZ | nullable |
| `created_at` | TIMESTAMPTZ | default now() |
| `updated_at` | TIMESTAMPTZ | default now() |

Indexes:
- GIN/trigram indexes for title/body/tags search

Rules:
- Soft delete
- Free memo = `variety_id is null`
- Variety-linked memo = `variety_id is not null`

---

### 7.2.8 `scraped_articles`
Purpose: scraped external information

| Column | Type | Constraints |
|---|---|---|
| `id` | UUID | PK |
| `source_key` | TEXT | NOT NULL |
| `source_name` | TEXT | NOT NULL |
| `listing_url` | TEXT | NOT NULL |
| `article_url` | TEXT | NOT NULL |
| `title` | TEXT | NOT NULL |
| `summary` | TEXT | NOT NULL |
| `article_hash` | TEXT | NOT NULL |
| `published_at` | TIMESTAMPTZ | nullable |
| `scraped_at` | TIMESTAMPTZ | default now() |
| `is_read` | BOOLEAN | default false |
| `read_at` | TIMESTAMPTZ | nullable |
| `related_variety_id` | UUID | nullable FK -> `varieties.id` |
| `raw_metadata` | JSONB | default `{}` |

Indexes/constraints:
- unique on `article_hash`
- optional unique on `article_url`
- index on `scraped_at desc`
- index on `source_key`
- trigram index on `title`, `summary`

Rules:
- `article_hash` must be SHA-256 of normalized content
- summary max stored length: 3000 characters
- display order default: newest first

---

### 7.2.9 `scrape_runs`
Purpose: overall scraper execution logs

| Column | Type | Constraints |
|---|---|---|
| `id` | UUID | PK |
| `trigger_type` | TEXT | `schedule`,`manual` |
| `status` | TEXT | `running`,`success`,`error`,`partial_success` |
| `github_run_id` | BIGINT | nullable |
| `github_run_url` | TEXT | nullable |
| `started_at` | TIMESTAMPTZ | NOT NULL |
| `finished_at` | TIMESTAMPTZ | nullable |
| `total_sources` | INTEGER | default 0 |
| `total_fetched` | INTEGER | default 0 |
| `total_inserted` | INTEGER | default 0 |
| `total_skipped` | INTEGER | default 0 |
| `error_message` | TEXT | nullable |

---

### 7.2.10 `scrape_source_logs`
Purpose: per-source scraper logs

| Column | Type | Constraints |
|---|---|---|
| `id` | UUID | PK |
| `scrape_run_id` | UUID | FK -> `scrape_runs.id`, NOT NULL |
| `source_key` | TEXT | NOT NULL |
| `source_name` | TEXT | NOT NULL |
| `status` | TEXT | `running`,`success`,`error`,`skipped` |
| `started_at` | TIMESTAMPTZ | NOT NULL |
| `finished_at` | TIMESTAMPTZ | nullable |
| `fetched_count` | INTEGER | default 0 |
| `inserted_count` | INTEGER | default 0 |
| `skipped_count` | INTEGER | default 0 |
| `error_message` | TEXT | nullable |

---

# 8. Database Functions and Constraints

## 8.1 Required Extensions
- `pgcrypto`
- `pg_trgm`

## 8.2 Required Functions
1. `update_updated_at_column()`
2. `is_admin()`
3. `would_create_pedigree_cycle(parent_uuid, child_uuid)`
4. `search_notes(search_query text)`

## 8.3 Cycle Detection Rule
When saving `variety_parent_links`, reject if:
- parent == child
- parent is already a descendant of child

This must be enforced:
1. in application validation
2. in DB trigger

---

# 9. Row Level Security (RLS)

## 9.1 Policy Model
### `app_users`
- authenticated users can select only their own row
- no app-side insert/update/delete

### All Other Tables
- only `is_admin()` returns true → access allowed
- all CRUD guarded

## 9.2 Storage Security
Create private buckets:
- `variety-images`
- `review-images`

Storage policies:
- admin only select/upload/update/delete
- app displays images using **signed URLs** with expiry 3600 seconds

---

# 10. UI / Page Specification

---

## 10.1 Global UI Rules
1. Use `st.set_page_config(layout="wide")`
2. Sidebar must show:
   - app name
   - current user email
   - logout button
3. All protected pages must call `require_admin_session()` first
4. All mutation actions must show:
   - success message
   - failure message
   - automatic rerun after success
5. After any create/update/delete/upload/read-toggle:
   - clear relevant caches

## 10.2 Pagination Standard
For list pages:
- default page size: 20
- selectable page size: 20 / 50 / 100
- manual pagination controls required

## 10.3 Empty State Standard
When no data exists:
- show `st.info("データがありません。")`
- show a clear next action button when relevant

---

## 10.4 `Home.py`
### Purpose
Login page if unauthenticated; dashboard if authenticated.

### Unauthenticated View
Fields:
- email
- password
Buttons:
- login

Behavior:
- login failure → error message
- unauthorized auth success → sign out + error message

### Authenticated Dashboard
Display:
- active varieties count
- active reviews count
- unread scraped articles count
- notes count
- average overall score
- last scrape run status
- latest 5 reviews
- latest 5 unread articles
- quick action buttons to pages

---

## 10.5 `pages/01_varieties.py`
### Sections
- Tab 1: List
- Tab 2: Create / Edit
- Tab 3: Deleted

### List Filters
- keyword (name, aliases, developer, description)
- prefecture
- tags
- sort field
- sort direction

### List Columns
- name
- alias summary
- prefecture
- developer
- registered year
- brix range
- acidity level
- harvest season
- review count
- average overall
- updated at

### Detail Panel
Selecting a row shows:
- all fields
- parent varieties
- child varieties
- primary image
- other images
- linked notes count
- linked reviews count

### Create/Edit Form Fields
- name (required)
- aliases (comma-separated input → array)
- prefecture (selectbox from fixed list)
- developer
- registered year
- description
- skin color
- flesh color
- brix min
- brix max
- acidity level
- harvest start month
- harvest end month
- tags (comma-separated)
- parent varieties (multi-select, exclude self, exclude deleted)
- crossed year per parent link (optional)
- breeding note per parent link (optional)
- images upload (0..5)
- primary image selection

### Validation
- name unique among active varieties
- brix_min <= brix_max
- months valid
- year valid
- max 20 tags
- max 20 aliases

### Delete Behavior
- soft delete only
- if linked active reviews exist, show warning with count
- allow delete after explicit confirmation

### Restore Behavior
- allowed only if no active variety with same name exists

---

## 10.6 `pages/02_reviews.py`
### Sections
- Tab 1: Create / Edit
- Tab 2: History
- Tab 3: Deleted

### Create/Edit Form Fields
- variety (required, active varieties only)
- tasted date (required, <= today)
- sweetness 1..5
- sourness 1..5
- aroma 1..5
- texture 1..5
- appearance 1..5
- overall 1..10
- purchase place
- price_jpy
- comment
- images upload (0..3)

### Validation
- all rating fields required
- price_jpy >= 0
- comment max 5000 chars

### Duplicate Handling
If active review exists for same `(variety_id, tasted_date)`:
- do not insert
- show dialog:
  - 「既存記録を更新する」
  - 「キャンセル」
- if user chooses update, overwrite existing review row

### History Filters
- variety
- date range
- overall min/max
- sort field
- sort direction

### History Columns
- tasted date
- variety name
- sweetness
- sourness
- aroma
- texture
- appearance
- overall
- purchase place
- price_jpy
- updated_at

### Delete Behavior
- soft delete only
- explicit confirmation required

### Restore Behavior
- allowed only if no active review with same `(variety_id, tasted_date)` exists

---

## 10.7 `pages/03_analytics.py`
### Global Filters
- review date range (default: last 12 months)
- prefecture
- tags
- selected varieties (optional)
- minimum review count (default 1)

### Charts
#### A. Radar Chart
- Dimensions: sweetness, sourness, aroma, texture, appearance
- Value: average per variety over filtered active reviews
- Max number of displayed varieties: 5
- If selected varieties empty, auto-pick top 3 by review count

#### B. Ranking Bar Chart
- Top 10 varieties by average overall
- Eligibility: filtered active reviews, min review count satisfied
- Tie-breaker: review count desc, then name asc

#### C. Monthly Time Series
- Line 1: monthly review count
- Line 2: monthly average overall
- Missing months must be filled with zero / null as appropriate

#### D. Scatter Plot
- X-axis: variety brix midpoint  
  `((brix_min + brix_max)/2)` if both exist, else existing bound
- Y-axis: average overall score
- One point per variety
- Marker size: review count
- Exclude varieties with no brix or no reviews

#### E. Prefecture Choropleth Map
- Use `assets/japan_prefectures.geojson`
- Metric: active variety count by prefecture
- Filters applied: prefecture/tag only
- Date filter does **not** affect this map
- Show note in UI explaining that

### Export
- Allow export of currently filtered analytics base data as CSV

---

## 10.8 `pages/04_pedigree.py`
### Purpose
Show breeding relationships as a directed acyclic graph

### Graph Library
- `networkx` for graph structure
- `plotly.graph_objects` for rendering
- `streamlit-plotly-events` for click capture

### Filters
- root variety (optional)
- direction: ancestors / descendants / both
- max depth: 1..5, default 3
- include deleted: default false

### Node Rules
- label = variety name
- color = average overall score gradient
  - no reviews: gray
  - low: light pink
  - high: dark red
- size = review count based scale
- customdata = variety_id

### Edge Rules
- direction parent -> child
- edge label = crossed year if available

### Interaction
- clicking a node sets `selected_variety_id` in session state
- redirect to `01_varieties.py`
- open the clicked variety detail panel

### Layout
- hierarchical top-down layout
- implement pure-Python layered layout
- do not require Graphviz system packages

### Error Handling
- if cycle somehow exists, show error banner and do not render graph

---

## 10.9 `pages/05_scraped_articles.py`
### Sections
- Filters row
- Articles list
- Read/unread actions

### Filters
- source
- keyword (title + summary)
- unread only
- related variety
- date range on scraped_at

### List Columns / Card Fields
- title
- summary (trimmed preview)
- source name
- published_at
- scraped_at
- related variety
- read/unread status
- external link button

### Actions
- mark one article as read/unread
- bulk mark filtered articles as read
- open article in new tab

### Sorting
- default `scraped_at desc`

---

## 10.10 `pages/06_notes.py`
### Sections
- Tab 1: List
- Tab 2: Create / Edit
- Tab 3: Deleted

### Form Fields
- title (required)
- body markdown (required)
- linked variety (optional)
- tags
- preview tab

### Search
- must search title, body, tags
- use DB-side search via RPC `search_notes`

### Validation
- title 1..200
- body 1..10000
- max 20 tags

### Delete
- soft delete only

### Restore
- always allowed unless future constraint added

---

## 10.11 `pages/07_settings.py`
### Sections
1. Data export
2. Manual scraper trigger
3. Recent scraper runs
4. Diagnostics

### Data Export
Provide separate download buttons for:
- varieties
- variety_parent_links
- reviews
- notes
- scraped_articles
- scrape_runs
- scrape_source_logs

CSV rules:
- UTF-8 with BOM
- arrays serialized by `|`
- timestamps converted to JST ISO8601

### Manual Scraper Trigger
UI fields:
- source selection: `all`, `maff`, `naro`, `ja_news`
- trigger button

Behavior:
- call GitHub Actions `workflow_dispatch`
- show dispatch success/failure
- poll latest workflow run status every 5 seconds for up to 2 minutes
- show run URL if available

### Diagnostics
Show:
- app version
- current timezone
- presence of required secrets (boolean only, never values)
- last successful scrape time

---

# 11. Input Validation Rules

## 11.1 Common
- Trim leading/trailing whitespace
- Convert internal consecutive spaces/newlines where appropriate
- Remove empty tags/aliases
- Deduplicate tags/aliases case-insensitively

## 11.2 Variety
- `name`: 1..100
- `developer`: 0..200
- `description`: 0..5000
- `registered_year`: 1900..current_year+1
- `brix_min`, `brix_max`: 0..30
- `harvest_start_month`, `harvest_end_month`: 1..12
- `tags`: max 20, each <=30 chars
- `alias_names`: max 20, each <=50 chars

## 11.3 Review
- `tasted_date <= today`
- ratings all required
- `purchase_place`: <=200
- `price_jpy`: 0..1000000
- `comment`: <=5000

## 11.4 Notes
- `title`: 1..200
- `body`: 1..10000
- `tags`: max 20, each <=30 chars

---

# 12. Image Upload Specification

## 12.1 Allowed Types
- JPG / JPEG
- PNG
- WEBP

## 12.2 Validation
1. file extension check
2. MIME type check
3. Pillow open validation
4. max original file size 50MB

## 12.3 Pre-upload Processing
- remove EXIF metadata
- resize long edge to max 2048 px
- keep aspect ratio
- JPEG quality 85 if saved as JPEG
- preserve PNG/WEBP when reasonable
- target recommended size under 4MB

## 12.4 Storage Paths
- Variety images: `varieties/{variety_id}/{uuid}_{safe_name}.{ext}`
- Review images: `reviews/{review_id}/{uuid}_{safe_name}.{ext}`

## 12.5 Display
- show thumbnails
- each thumbnail has an explicit `Open` button
- open full-size image in dialog
- image URLs must be signed URLs, expiry 3600 seconds

## 12.6 Delete
- deleting an image removes:
  1. storage object
  2. DB metadata row

---

# 13. Search Specification

## 13.1 Variety Search
Search targets:
- name
- aliases
- developer
- description

## 13.2 Note Search
Search targets:
- title
- body
- tags

Implementation:
- DB RPC `search_notes(search_query text)`

## 13.3 Scraped Article Search
Search targets:
- title
- summary

---

# 14. Scraping Specification

## 14.1 Initial Implemented Sources
Only the following sources are mandatory in v2.0.0:
1. MAFF
2. NARO
3. JA News

Other candidate sources remain future extension only.

## 14.2 Legal / Politeness Rules
For every source:
1. check `robots.txt`
2. scrape only if allowed
3. use custom User-Agent
4. minimum 5 seconds between external HTTP requests
5. timeout 20 seconds
6. retry up to 3 times with exponential backoff
7. sequential requests only
8. no headless browser
9. no bypass of anti-bot mechanisms

## 14.3 Source Config
Each source config must include:
- `source_key`
- `source_name`
- `enabled`
- `listing_urls`
- `min_interval_seconds`
- `max_articles_per_run`

## 14.4 Parser Interface
Every source scraper class must implement:
- `fetch_article_links() -> list[str]`
- `fetch_article(article_url: str) -> dict`
- `run() -> list[dict]`

Normalized article dict fields:
- `source_key`
- `source_name`
- `listing_url`
- `article_url`
- `title`
- `summary`
- `published_at`
- `raw_metadata`

## 14.5 Normalization
Before saving:
- Unicode normalize NFKC
- trim whitespace
- collapse repeated spaces/newlines
- strip HTML remnants
- truncate summary to 3000 chars

## 14.6 Duplicate Detection
`article_hash = sha256(normalized_article_url + "\n" + normalized_title + "\n" + normalized_summary)`

## 14.7 Related Variety Resolution
Attempt exact match against:
- active variety `name`
- any active `alias_names`

If:
- exactly one match → set `related_variety_id`
- none or multiple → set null

## 14.8 Run Logging
For each run:
- create `scrape_runs` row at start
- create `scrape_source_logs` row per source
- update statuses in finally blocks

## 14.9 Failure Rules
- one source failure must not stop other sources
- overall run status:
  - all success → `success`
  - mix of success/error → `partial_success`
  - all failed → `error`

---

# 15. GitHub Actions Workflow Specification

## 15.1 File
`.github/workflows/scrape.yml`

## 15.2 Triggers
- schedule: daily at `06:00 JST` (`21:00 UTC`)
- workflow_dispatch:
  - input `source` default `all`

## 15.3 Jobs
### Job A: `scrape`
Responsibilities:
- checkout
- setup Python 3.12
- install `requirements-scraper.txt`
- run `python scraper/main.py --source <input_or_all>`

Env:
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `APP_TIMEZONE`
- GitHub run metadata if available

### Job B: `heartbeat`
Responsibilities:
- always run, even if scrape failed
- ping Supabase to avoid inactivity pause

Must include:
- `if: always()`

## 15.4 Workflow Requirements
- heartbeat must not depend on scrape success
- scraper logs must still be finalized on exception
- workflow must be safe for public repo use with secrets

---

# 16. Service Layer Responsibilities

## 16.1 `auth_service.py`
- login
- logout
- current session validation
- `require_admin_session()`

## 16.2 `variety_service.py`
- create/update/delete/restore variety
- search/filter/sort/paginate
- manage parent links
- fetch detail stats

## 16.3 `review_service.py`
- create/update/delete/restore review
- duplicate detection
- filter/sort/paginate

## 16.4 `analytics_service.py`
- assemble filtered datasets
- compute radar/ranking/timeseries/scatter/map data

## 16.5 `pedigree_service.py`
- build subgraph
- layered layout coordinates
- node color/size calculations
- cycle safeguard checks

## 16.6 `note_service.py`
- CRUD
- search via RPC
- paginate

## 16.7 `scrape_service.py`
- list articles
- mark read/unread
- bulk mark read
- fetch run history
- dispatch GitHub workflow
- poll workflow status

## 16.8 `storage_service.py`
- validate image
- resize/compress
- upload/delete
- create signed URLs

## 16.9 `export_service.py`
- query target dataset
- normalize arrays/timestamps
- produce CSV bytes with BOM

---

# 17. Non-functional Requirements

## 17.1 Performance
Given:
- 500 varieties
- 2,000 reviews
- 10,000 scraped articles

Targets:
- page render: under 3 seconds for normal pages
- analytics page: under 5 seconds
- CSV export start: under 10 seconds
- scraper total daily run: under 15 minutes

## 17.2 Caching
- use `st.cache_data(ttl=300)` for read-heavy queries
- use `st.cache_resource` for static clients/config
- clear relevant cache after mutations

## 17.3 Timezone
- DB stores UTC
- UI displays JST (`Asia/Tokyo`)
- CSV timestamps exported in JST ISO8601

## 17.4 Logging
- app logs to stdout
- scraper logs to stdout + DB log tables
- never log secrets or passwords

---

# 18. Dependency Specification

## 18.1 `requirements.txt`
Recommended ranges:

```txt
streamlit>=1.35,<2.0
supabase>=2.4,<3.0
pandas>=2.2,<3.0
plotly>=5.20,<6.0
networkx>=3.2,<4.0
streamlit-plotly-events>=0.0.6,<1.0
pillow>=10.0,<12.0
requests>=2.31,<3.0
python-dateutil>=2.9,<3.0
```

## 18.2 `requirements-scraper.txt`
```txt
requests>=2.31,<3.0
beautifulsoup4>=4.12,<5.0
lxml>=5.0,<6.0
supabase>=2.4,<3.0
python-dateutil>=2.9,<3.0
tenacity>=8.2,<9.0
```

## 18.3 `requirements-dev.txt`
```txt
pytest>=8.0,<9.0
pytest-mock>=3.0,<4.0
```

---

# 19. Streamlit Config

## `.streamlit/config.toml`
```toml
[theme]
primaryColor = "#E8334A"
backgroundColor = "#FFFAF0"
secondaryBackgroundColor = "#FFE4E1"
textColor = "#333333"
font = "sans serif"

[server]
maxUploadSize = 50
```

---

# 20. Database Migration Order

Run in this order:

1. `database/000_extensions.sql`
2. `database/001_functions.sql`
3. `database/002_tables.sql`
4. `database/003_indexes.sql`
5. `database/004_rls.sql`
6. `database/005_storage.sql`
7. `database/006_rpc.sql`
8. `database/007_seed_admin.sql.template` (after creating auth user)

---

# 21. Admin Bootstrap Procedure

1. Create Supabase Auth user manually
2. Get the created `auth.users.id`
3. Insert into `app_users`

Template:
```sql
insert into public.app_users (user_id, email, role)
select id, email, 'admin'
from auth.users
where email = 'your-email@example.com';
```

---

# 22. Testing Requirements

## 22.1 Unit Tests
Must implement tests for:
- validation rules
- image resize/format validation
- article hashing normalization
- pedigree cycle detection logic
- CSV export encoding and field formatting

## 22.2 Manual Acceptance Tests
### Auth
- unauthorized access blocked
- authorized login works
- logout works

### Varieties
- create/edit/delete/restore
- parent link save
- duplicate name blocked
- deleted varieties hidden from create review dropdown

### Reviews
- create/edit/delete/restore
- duplicate same day behavior updates existing
- analytics reflects changes

### Analytics
- all charts render with sample data
- filters work
- map renders correctly

### Pedigree
- graph renders
- click navigation works
- cycle cannot be created

### Scraped Articles
- read/unread toggles persist
- filters work
- external link opens

### Notes
- markdown preview works
- search works
- delete/restore works

### Settings
- CSV downloads are valid UTF-8 BOM
- manual scraper dispatch works if token configured

---

# 23. Definition of Done

This project is complete only if all of the following are true:

1. All pages are implemented with the specified English filenames
2. All DB tables, indexes, functions, RPC, and RLS policies exist
3. Only the seeded admin user can access data
4. Soft delete/restore works for varieties, reviews, notes
5. Image upload/display/delete works with private buckets + signed URLs
6. Review duplicate rule is enforced exactly as specified
7. Pedigree graph is clickable and cycle-safe
8. Scraper runs on schedule and writes logs
9. Manual scrape dispatch works from settings page
10. CSV exports work for all specified datasets
11. Tests pass
12. No secrets are committed

---

# 24. Implementation Notes for Copilot CLI

Use these rules strictly:

1. Generate the project using the directory structure in Section 3.
2. Use English filenames only.
3. Keep UI labels Japanese where meaningful, but keep code identifiers English.
4. Implement all pages as Streamlit multipage files.
5. Do not introduce frameworks outside the approved stack.
6. Prefer small service modules over massive page files.
7. Add type hints to all public functions.
8. Add docstrings to services and utilities.
9. Use partial unique indexes for soft-delete-aware uniqueness.
10. Use private Supabase storage buckets and signed URLs.
11. Use Plotly for pedigree graph rendering, not PyVis.
12. Enforce DAG integrity at both app layer and DB layer.
13. Respect robots.txt and rate limiting in scraper.

---

# 25. Recommended Implementation Order

1. Database migrations
2. Auth service + page guards
3. Variety CRUD
4. Review CRUD
5. Image upload
6. Analytics page
7. Pedigree page
8. Notes page
9. Scraped articles page
10. Settings page
11. Scraper + GitHub Actions
12. Tests and polish
