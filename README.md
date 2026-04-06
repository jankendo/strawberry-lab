# StrawberryLab

Private single-user Streamlit app for strawberry variety research, tasting reviews, analytics, pedigree visualization, notes, and scraper ingestion.

## Stack
- Python 3.12
- Streamlit
- Supabase (PostgreSQL/Auth/Storage)
- GitHub Actions (scraper schedule)

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

## Run app
- `streamlit run Home.py`

## Run scraper locally
- `python scraper/main.py --source all`
- `python scraper/main.py --source maff`

## Run tests
- `pytest -q`
