# StrawberryLab

Private single-user Streamlit app for strawberry variety research, tasting reviews, analytics, pedigree visualization, notes, and MAFF variety-registry ingestion.

## Stack
- Python 3.12
- Streamlit
- Supabase (PostgreSQL/Auth/Storage)

## Local setup
1. Install dependencies:
   - `pip install -r requirements.txt`
   - `pip install -r requirements-scraper.txt`
   - `pip install -r requirements-dev.txt`
2. Copy `.streamlit/secrets.example.toml` to `.streamlit/secrets.toml` and set real values.
3. Apply SQL migrations in Supabase SQL Editor in this order:
   1. `database/000_extensions.sql`
   2. `database/001_functions.sql`
   3. `database/002_tables.sql`
   4. `database/003_indexes.sql`
   5. `database/004_rls.sql`
   6. `database/005_storage.sql`
   7. `database/006_rpc.sql`
   8. `database/007_seed_admin.sql.template` (after auth user creation)
   - Existing article-scrape tables are dropped by `002_tables.sql`.

## Run app
- `streamlit run Home.py`

## Run MAFF variety scraper locally (fast mode)
PowerShell:

```powershell
$env:SUPABASE_URL = "https://YOUR_PROJECT.supabase.co"
$env:SUPABASE_SERVICE_ROLE_KEY = "YOUR_SERVICE_ROLE_KEY"
$env:APP_TIMEZONE = "Asia/Tokyo"
$env:MAFF_MIN_INTERVAL_SECONDS = "0"
$env:MAFF_MAX_PAGES_PER_RUN = "200"
$env:MAFF_FETCH_IMAGES = "1"
$env:MAFF_MAX_IMAGES_PER_VARIETY = "3"
$env:SUPABASE_UPSERT_BATCH_SIZE = "200"
python -m scraper.main
```

- Optional heartbeat check: `python -m scraper.heartbeat`
- MAFF詳細画像は `variety-images` バケットへ同期され、`variety_images` テーブルへメタデータ保存されます。
- If schema-related errors occur, re-apply `database/supabase_all_in_one.sql`.

## Run tests
- `pytest -q`
