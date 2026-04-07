# Copilot instructions for this repository

## Build, test, lint, and run commands

| Task | Command |
| --- | --- |
| Install app dependencies | `pip install -r requirements.txt` |
| Install scraper dependencies | `pip install -r requirements-scraper.txt` |
| Install dev/test dependencies | `pip install -r requirements-dev.txt` |
| Run Streamlit app | `streamlit run Home.py` |
| Run all tests | `pytest -q` |
| Run one test file | `pytest -q tests/test_review_service.py` |
| Run one test case | `pytest -q tests/test_review_service.py::test_create_or_update_review_raises_duplicate_without_overwrite` |
| Run MAFF scraper locally | `python -m scraper.main` |
| Import pedigree CSV | `python -m scraper.import_pedigree_links` |

SQL migrations are applied in Supabase SQL Editor in this order: `database/000_extensions.sql` -> `001_functions.sql` -> `002_tables.sql` -> `003_indexes.sql` -> `004_rls.sql` -> `005_storage.sql` -> `006_rpc.sql` -> `007_seed_admin.sql.template`.

There is no dedicated lint command configured in this repository.

## High-level architecture

1. **Streamlit app shell + page entrypoints**
   - `Home.py` is the auth/bootstrap and dashboard entrypoint.
   - Feature pages live in `pages/01_varieties.py`, `02_reviews.py`, `03_analytics.py`, `04_pedigree.py`, `07_settings.py`.
   - Shared UI primitives (hero, badges, empty states, mobile behavior, styling) are centralized in `src/components/layout.py` and `src/components/sidebar.py`.

2. **Service layer for business/data operations**
   - `src/services/*.py` is the main application layer used by pages.
   - Services encapsulate Supabase table access, filtering, pagination, domain rules, and cache behavior.
   - Auth/session state lives in `src/services/auth_service.py`; data access uses the authenticated client via `get_user_client()`.

3. **Caching and invalidation model**
   - Read paths are mostly wrapped with `@scoped_cache_data(...)` from `src/services/cache_service.py`.
   - Mutations clear affected cached functions and also call `bump_cache_scopes(...)` so stale data is invalidated across pages.
   - Cache scope revisions can be local-memory or Redis-backed (`CACHE_REDIS_URL`, optional `CACHE_NAMESPACE`).

4. **Database + policy model**
   - Schema is managed with SQL files under `database/`.
   - RLS is enabled for app tables and access is gated by `public.is_admin()` (`database/004_rls.sql`).
   - Important DB invariants are enforced in SQL functions/triggers (`database/001_functions.sql`), including pedigree DAG checks and image-count limits.

5. **Scraper subsystem**
   - `scraper/sources/maff_scraper.py` crawls MAFF listing/detail pages.
   - `scraper/main.py` writes run/log records and upserts varieties (plus MAFF image sync).
   - `scraper/import_pedigree_links.py` performs idempotent CSV import for `variety_parent_links`.
   - CI workflows in `.github/workflows/scrape.yml` and `import-pedigree-links.yml` run these jobs.

## Key conventions specific to this codebase

1. **Page bootstrap order is consistent**
   - For protected pages: `st.set_page_config(...)` -> `require_admin_session()` -> `inject_app_style()` -> `render_sidebar(...)` -> `render_primary_nav(...)`.
   - `Home.py` performs auth initialization/restoration before rendering dashboard/login.

2. **Use service-layer operations; do not query tables directly in new page code unless following existing service patterns**
   - Keep CRUD and rules in `src/services/*`, not scattered in pages.

3. **Soft-delete is the default data lifecycle**
   - `varieties` and `reviews` use `deleted_at` for archive/restore flows.
   - Active-query paths consistently filter with `.is_("deleted_at", "null")`.

4. **Validate payloads before writes**
   - Use `validate_variety_payload` and `validate_review_payload` in `src/utils/validation.py` before insert/update logic.

5. **Cache invalidation is mandatory for mutations**
   - When adding/changing mutating service functions, clear related cached functions and bump relevant scopes.
   - Some mutations also invalidate cross-feature caches (for example export/pedigree/analytics scopes).

6. **Keep pedigree integrity checks in both app and DB layers**
   - App layer uses NetworkX checks before inserting parent links.
   - DB trigger/function (`enforce_pedigree_dag`) remains the final guardrail.

7. **Image handling goes through `storage_service`**
   - Upload paths should use validation + processing helpers (`validate_image_file`, `process_image`).
   - Respect enforced limits (variety images: 5, review images: 3).

8. **Review save flow includes offline intent queue + draft buffering**
   - `src/components/offline_queue.py` and `draft_buffer.py` patterns are intentionally used for resilient saves.
   - Preserve these flows when modifying save UX on `pages/02_reviews.py`.

9. **UI/navigation is intentionally custom**
   - `.streamlit/config.toml` sets `showSidebarNavigation = false`.
   - Navigation should use internal sidebar/bottom-nav components instead of default Streamlit multipage sidebar.

10. **Localization**
   - User-facing labels/copy are primarily Japanese; keep language and tone consistent in new UI text.

11. **Secrets boundary**
   - `.streamlit/secrets.toml` is for client-side app settings (`SUPABASE_URL`, `SUPABASE_ANON_KEY`, app config).
   - Do **not** put `SUPABASE_SERVICE_ROLE_KEY` in Streamlit app secrets; service-role usage is for scraper/admin contexts.
