create extension if not exists pgcrypto;

create type public.product_type as enum ('fisico', 'digital');
create type public.partner_name as enum ('amazon', 'shopee', 'mercado_livre');
create type public.stock_status as enum ('disponivel', 'indisponivel', 'informativo');
create type public.sync_status as enum ('running', 'success', 'partial', 'failed');

create table public.products (
  id text primary key check (id ~ '^[A-Za-z0-9][A-Za-z0-9._-]*$'),
  name text not null check (char_length(name) between 1 and 180),
  slug text not null unique check (slug ~ '^[a-z0-9]+(?:-[a-z0-9]+)*$'),
  category text not null check (char_length(category) between 1 and 80),
  type public.product_type not null,
  short_description text not null check (char_length(short_description) between 1 and 280),
  description text not null check (char_length(description) between 1 and 5000),
  current_price numeric(12, 2) not null check (current_price > 0),
  previous_price numeric(12, 2),
  currency text not null default 'BRL' check (currency = 'BRL'),
  primary_image text not null,
  images text[] not null default '{}',
  partner public.partner_name not null,
  affiliate_url text not null check (affiliate_url ~ '^https://'),
  featured boolean not null default false,
  active boolean not null default true,
  stock_status public.stock_status not null default 'informativo',
  tags text[] not null default '{}',
  updated_at timestamptz not null,
  synced_at timestamptz not null default now(),
  constraint valid_previous_price check (previous_price is null or previous_price > current_price)
);

create table public.sync_runs (
  id uuid primary key default gen_random_uuid(),
  status public.sync_status not null default 'running',
  started_at timestamptz not null default now(),
  finished_at timestamptz,
  rows_read integer not null default 0 check (rows_read >= 0),
  inserted_count integer not null default 0 check (inserted_count >= 0),
  updated_count integer not null default 0 check (updated_count >= 0),
  rejected_count integer not null default 0 check (rejected_count >= 0),
  deactivated_count integer not null default 0 check (deactivated_count >= 0),
  error_summary jsonb not null default '[]'::jsonb check (jsonb_typeof(error_summary) = 'array')
);

create table public.affiliate_clicks (
  id bigint generated always as identity primary key,
  product_id text not null references public.products(id) on delete restrict,
  partner public.partner_name not null,
  clicked_at timestamptz not null default now()
);

create table public.affiliate_click_daily (
  click_date date not null,
  product_id text not null,
  partner public.partner_name not null,
  click_count bigint not null check (click_count >= 0),
  primary key (click_date, product_id, partner)
);

create index products_active_category_idx on public.products (category, updated_at desc) where active;
create index products_active_partner_idx on public.products (partner, current_price) where active;
create index products_tags_idx on public.products using gin (tags);
create index affiliate_clicks_clicked_at_idx on public.affiliate_clicks (clicked_at);
create index affiliate_clicks_product_idx on public.affiliate_clicks (product_id, clicked_at desc);

alter table public.products enable row level security;
alter table public.sync_runs enable row level security;
alter table public.affiliate_clicks enable row level security;
alter table public.affiliate_click_daily enable row level security;

revoke all on public.products from anon, authenticated;
revoke all on public.sync_runs from anon, authenticated;
revoke all on public.affiliate_clicks from anon, authenticated;
revoke all on public.affiliate_click_daily from anon, authenticated;

create policy "active products are readable"
on public.products
for select
to anon, authenticated
using (active = true);

grant select (
  id,
  name,
  slug,
  category,
  type,
  short_description,
  description,
  current_price,
  previous_price,
  currency,
  primary_image,
  images,
  partner,
  featured,
  active,
  stock_status,
  tags,
  updated_at
) on public.products to anon, authenticated;

create or replace function public.apply_catalog_snapshot(
  p_run_id uuid,
  p_products jsonb,
  p_preserved_ids text[],
  p_rows_read integer,
  p_rejected integer
)
returns jsonb
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  v_inserted integer := 0;
  v_updated integer := 0;
  v_deactivated integer := 0;
begin
  if jsonb_typeof(p_products) <> 'array' then
    raise exception 'invalid snapshot';
  end if;

  perform pg_advisory_xact_lock(hashtext('orvani_catalog_sync'));

  if not exists (
    select 1 from public.sync_runs where id = p_run_id and status = 'running'
  ) then
    raise exception 'invalid sync run';
  end if;

  with incoming as (
    select *
    from jsonb_to_recordset(p_products) as item(
      id text,
      name text,
      slug text,
      category text,
      type public.product_type,
      short_description text,
      description text,
      current_price numeric,
      previous_price numeric,
      currency text,
      primary_image text,
      images text[],
      partner public.partner_name,
      affiliate_url text,
      featured boolean,
      active boolean,
      stock_status public.stock_status,
      tags text[],
      updated_at timestamptz
    )
  ), upserted as (
    insert into public.products as stored (
      id, name, slug, category, type, short_description, description,
      current_price, previous_price, currency, primary_image, images,
      partner, affiliate_url, featured, active, stock_status, tags, updated_at, synced_at
    )
    select
      id, name, slug, category, type, short_description, description,
      current_price, previous_price, currency, primary_image, images,
      partner, affiliate_url, featured, active, stock_status, tags, updated_at, now()
    from incoming
    on conflict (id) do update set
      name = excluded.name,
      slug = excluded.slug,
      category = excluded.category,
      type = excluded.type,
      short_description = excluded.short_description,
      description = excluded.description,
      current_price = excluded.current_price,
      previous_price = excluded.previous_price,
      currency = excluded.currency,
      primary_image = excluded.primary_image,
      images = excluded.images,
      partner = excluded.partner,
      affiliate_url = excluded.affiliate_url,
      featured = excluded.featured,
      active = excluded.active,
      stock_status = excluded.stock_status,
      tags = excluded.tags,
      updated_at = excluded.updated_at,
      synced_at = now()
    where (
      stored.name, stored.slug, stored.category, stored.type, stored.short_description,
      stored.description, stored.current_price, stored.previous_price, stored.currency,
      stored.primary_image, stored.images, stored.partner, stored.affiliate_url,
      stored.featured, stored.active, stored.stock_status, stored.tags, stored.updated_at
    ) is distinct from (
      excluded.name, excluded.slug, excluded.category, excluded.type, excluded.short_description,
      excluded.description, excluded.current_price, excluded.previous_price, excluded.currency,
      excluded.primary_image, excluded.images, excluded.partner, excluded.affiliate_url,
      excluded.featured, excluded.active, excluded.stock_status, excluded.tags, excluded.updated_at
    )
    returning (xmax = 0) as was_inserted
  )
  select
    count(*) filter (where was_inserted),
    count(*) filter (where not was_inserted)
  into v_inserted, v_updated
  from upserted;

  update public.products as stored
  set active = false, synced_at = now()
  where stored.active = true
    and not exists (
      select 1
      from jsonb_array_elements(p_products) as item
      where item ->> 'id' = stored.id
    )
    and not (stored.id = any(coalesce(p_preserved_ids, array[]::text[])));
  get diagnostics v_deactivated = row_count;

  update public.sync_runs
  set
    status = case when p_rejected > 0 then 'partial'::public.sync_status else 'success'::public.sync_status end,
    finished_at = now(),
    rows_read = p_rows_read,
    inserted_count = v_inserted,
    updated_count = v_updated,
    rejected_count = p_rejected,
    deactivated_count = v_deactivated
  where id = p_run_id;

  return jsonb_build_object(
    'inserted', v_inserted,
    'updated', v_updated,
    'deactivated', v_deactivated
  );
end;
$$;

revoke execute on function public.apply_catalog_snapshot(uuid, jsonb, text[], integer, integer) from public;
grant execute on function public.apply_catalog_snapshot(uuid, jsonb, text[], integer, integer) to service_role;

create or replace function public.aggregate_and_prune_affiliate_clicks(
  cutoff timestamptz default now() - interval '90 days'
)
returns bigint
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  removed bigint := 0;
begin
  insert into public.affiliate_click_daily (click_date, product_id, partner, click_count)
  select
    (clicked_at at time zone 'America/Bahia')::date,
    product_id,
    partner,
    count(*)
  from public.affiliate_clicks
  where clicked_at < cutoff
  group by (clicked_at at time zone 'America/Bahia')::date, product_id, partner
  on conflict (click_date, product_id, partner)
  do update set click_count = public.affiliate_click_daily.click_count + excluded.click_count;

  delete from public.affiliate_clicks where clicked_at < cutoff;
  get diagnostics removed = row_count;
  return removed;
end;
$$;

revoke execute on function public.aggregate_and_prune_affiliate_clicks(timestamptz) from public;
grant execute on function public.aggregate_and_prune_affiliate_clicks(timestamptz) to service_role;
