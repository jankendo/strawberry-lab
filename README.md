# StrawberryLab

Private single-user Streamlit app for strawberry variety research, tasting reviews, analytics, pedigree visualization, and MAFF variety-registry ingestion.

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
    - `APP_HIDE_HOST_CHROME` を `true` にすると、Streamlitホスト由来の上部ツールUIを非表示にします（既定値は `true`）。
   - マルチインスタンス運用でキャッシュ無効化を共有したい場合は `CACHE_REDIS_URL`（任意で `CACHE_NAMESPACE`）を設定してください。
   - Redis未設定時はプロセスローカル無効化で動作します。必要に応じて `APP_EXPECT_STICKY_SESSIONS=true` の前提で同一ユーザーを同一インスタンスへ固定してください。
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
- **All-page UI refresh**: Home / 品種管理 / 試食評価 / 分析 / 交配図 / 設定 now share upgraded header, card, and section styling for a more consistent experience.

## v7 updates (UX / behavior)
- **Quick actions on Home**: dashboard now highlights one-click page shortcuts and follow-up links for review/log operations.
- **Consistent empty states**: Home / 品種管理 / 試食評価 / 分析 / 交配図 / 設定 show guided empty-state cards with next steps.
- **Pedigree graph readability**: denser lineage graphs use improved layout spacing, viewport sizing, and click navigation reliability.

## v8 updates (UI redesign)
- **Neutral-first design system**: default input/background now uses neutral colors, with strawberry accent reserved for primary actions and focus states.
- **Sidebar hierarchy refresh**: active page is highlighted, and account actions (設定/ログアウト) are grouped in the user area.
- **Information architecture updates**: Home / 品種管理 / 試食評価 / 分析 / 交配図 / 設定 were reorganized for stronger action priority, clearer empty states, and improved table readability.

## v9 updates (native shell / PWA)
- **Progressive native shell enhancement**: `inject_app_style()` now injects head metadata (manifest/theme/iOS web-app tags), touch icons, and guarded iOS scroll behavior.
- **Service worker support**: a conservative static-shell cache worker (`static/app-sw.js`) now uses versioned cache rotation, same-origin matching for `/app/static/` + `/static/`, and lightweight `ichigodb:network-status` messages for optional offline indicators.
- **Static asset serving**: `.streamlit/config.toml` enables `enableStaticServing = true` for manifest/icon/service-worker delivery.

## v10 updates (image pipeline acceleration)
- **Client-side image optimization**: new `asset_uploader` component resizes and compresses images in-browser (long edge 2048px / WebP) before upload.
- **Direct upload flow**: review/variety pages now use signed upload URLs and browser-to-Supabase direct PUT, then finalize metadata rows in `variety_images` / `review_images`.
- **Retry-aware UX**: upload results are tracked in component state, with replay-event retry hooks for transient network failures.

## Access mode
- This app now runs in **public mode** by default and no longer requires an interactive login step.
- To keep behavior equivalent to the former admin-login flow, apply the updated `database/004_rls.sql` **and** `database/005_storage.sql` (or `database/supabase_all_in_one.sql`) so the anon role can access both the application tables and image storage.
- The settings page now includes **全テーブル接続チェック** and **画像ストレージ接続チェック** panels to confirm runtime access for both tables and image storage.

## Cache invalidation / scale behavior
- Data caches are partitioned by authenticated user scope and revision tokens.
- Write operations bump revision tokens and clear local cache entries so cross-page stale UX is reduced immediately.
- `CACHE_REDIS_URL` を設定すると、複数インスタンス間で無効化トークンを共有できます（未設定時はローカル無効化）。
- `APP_EXPECT_STICKY_SESSIONS`（既定 `true`）で、Redis未使用時のセッション固定前提を診断表示に反映できます。

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

## Sync pedigree research CSV
PowerShell:

```powershell
$env:SUPABASE_URL = "https://YOUR_PROJECT.supabase.co"
$env:SUPABASE_SERVICE_ROLE_KEY = "YOUR_SERVICE_ROLE_KEY"
$env:PEDIGREE_SOURCE_CSV_PATH = "strawberry_full_pedigree.csv"
$env:PEDIGREE_IMPORT_CSV_PATH = "database/imports/variety_parent_links.csv"
python -m scraper.create_placeholder_varieties_for_pedigree
python -m scraper.build_pedigree_links_from_name_csv
python -m scraper.import_pedigree_links
```

- `strawberry_full_pedigree.csv` を source of truth とし、既存品種で解決できない child / parent 名は `pedigree_placeholder` の仮登録品種として先に追加します。
- オフラインで import artifact だけ再生成したい場合は `PEDIGREE_VARIETIES_CSV_PATH=varieties_rows.csv` を設定して `python -m scraper.build_pedigree_links_from_name_csv` を実行してください。
- GitHub Actions の `import-pedigree-links` workflow も同じ順序で placeholder 作成 → UUID CSV 生成 → `variety_parent_links` import を行います。

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
