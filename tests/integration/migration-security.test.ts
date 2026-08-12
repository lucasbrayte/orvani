import { readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

const sql = readFileSync("supabase/migrations/202608110001_orvani_catalog.sql", "utf8");

describe("catalog migration", () => {
  it.each(["products", "sync_runs", "affiliate_clicks", "affiliate_click_daily"])(
    "enables RLS on %s",
    (table) => {
      expect(sql).toMatch(
        new RegExp(`alter table public\\.${table} enable row level security`, "i"),
      );
    },
  );

  it("does not grant public access to affiliate URLs or metrics", () => {
    expect(sql).toMatch(/revoke all on public\.sync_runs from anon, authenticated/i);
    expect(sql).toMatch(/revoke all on public\.affiliate_clicks from anon, authenticated/i);
    expect(sql).not.toMatch(/grant select \([^)]*affiliate_url[^)]*\) on public\.products to anon/i);
  });

  it("restricts administrative functions to the service role", () => {
    expect(sql).toMatch(/revoke execute on function public\.apply_catalog_snapshot[\s\S]*from public/i);
    expect(sql).toMatch(/grant execute on function public\.apply_catalog_snapshot[\s\S]*to service_role/i);
    expect(sql).toMatch(/aggregate_and_prune_affiliate_clicks/i);
  });
});
