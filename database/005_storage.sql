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

drop policy if exists public_select_variety_images on storage.objects;
create policy public_select_variety_images
on storage.objects
for select
to anon
using (bucket_id = 'variety-images');

drop policy if exists public_write_variety_images on storage.objects;
create policy public_write_variety_images
on storage.objects
for all
to anon
using (bucket_id = 'variety-images')
with check (bucket_id = 'variety-images');

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

drop policy if exists public_select_review_images on storage.objects;
create policy public_select_review_images
on storage.objects
for select
to anon
using (bucket_id = 'review-images');

drop policy if exists public_write_review_images on storage.objects;
create policy public_write_review_images
on storage.objects
for all
to anon
using (bucket_id = 'review-images')
with check (bucket_id = 'review-images');
