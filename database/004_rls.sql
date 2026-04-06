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
