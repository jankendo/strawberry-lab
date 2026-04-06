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
   - `APP_COOKIE_SECRET` を設定すると、ログイン状態を30日安定して保持できます（未設定時は一時ランダム秘密鍵へフォールバックし、再起動/再デプロイで保持がリセットされる場合があります）。
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

## v4 updates (UI / behavior)
- **Review save stability**: fixed a crash path when creating a review if the insert response does not return row data.
- **Sidebar navigation cleanup**: removed Streamlit's default multipage sidebar menu (`showSidebarNavigation = false`) to avoid duplicate navigation entries.
- **All-page UI refresh**: Home / 品種管理 / 試食評価 / 分析 / 交配図 / 研究メモ / 設定 now share upgraded header, card, and section styling for a more consistent experience.

## v7 updates (UX / behavior)
- **Quick actions on Home**: dashboard now highlights one-click page shortcuts and follow-up links for review/log operations.
- **Consistent empty states**: Home / 品種管理 / 試食評価 / 分析 / 交配図 / 研究メモ / 設定 show guided empty-state cards with next steps.
- **Pedigree graph readability**: denser lineage graphs use improved layout spacing, viewport sizing, and click navigation reliability.

## Login persistence (30 days)
- This app supports login skip on revisit by storing encrypted auth session cookies.
- For stable persistence across restarts, set:
  - `APP_COOKIE_SECRET` in `.streamlit/secrets.toml` (long random string)
- If `APP_COOKIE_SECRET` is missing, the app falls back to a process-local temporary random secret and shows a UI warning/diagnostic. Persistence can reset on app restart/redeploy.
- Logout always clears the persisted cookie.

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

## Pedigree configuration guide
1. Open **品種管理** → **作成・編集** and set one or more **親品種** for each child variety.
2. Save, then open **交配図**.
3. Choose:
   - **起点品種**: node to focus
   - **表示方向**: ancestors / descendants / both
   - **最大深さ**: visible generation depth
4. Click any node on the graph to jump to the selected variety detail.
5. If you get a cycle error, review parent links and remove loops.

## Run tests
- `pytest -q`
