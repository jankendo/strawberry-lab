create or replace function public.search_notes(search_query text)
returns setof public.notes
language sql
stable
security definer
set search_path = public
as $$
  select n.*
  from public.notes n
  where
    coalesce(search_query, '') = ''
    or n.title ilike '%' || search_query || '%'
    or n.body ilike '%' || search_query || '%'
    or exists (
      select 1
      from unnest(n.tags) as t
      where t ilike '%' || search_query || '%'
    )
  order by n.updated_at desc;
$$;
