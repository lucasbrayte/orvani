import { createClient, type SupabaseClient } from "@supabase/supabase-js";

import { getRuntimeEnv } from "@/config/env";

const options = {
  auth: {
    autoRefreshToken: false,
    persistSession: false,
    detectSessionInUrl: false,
  },
} as const;

export function createSupabaseReadClient(): SupabaseClient {
  const env = getRuntimeEnv();
  if (!env.supabase) throw new Error("Supabase não configurado para leitura.");
  return createClient(env.supabase.url, env.supabase.publishableKey, options);
}

export function createSupabaseAdminClient(): SupabaseClient {
  const env = getRuntimeEnv();
  if (!env.supabase) throw new Error("Supabase não configurado para administração.");
  return createClient(env.supabase.url, env.supabase.secretKey, options);
}
