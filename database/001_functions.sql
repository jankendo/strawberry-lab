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
