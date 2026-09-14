import { createClient, type SupabaseClient } from '@supabase/supabase-js';

const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

/** Cliente so para LOGIN e sessao. Os dados do produto continuam a vir apenas
 *  da nossa API. A anon key e publica por desenho: com RLS ligado e nenhuma
 *  politica para ela, nao le nem escreve nenhuma tabela.
 *
 *  Sem as variaveis configuradas fica null e o site funciona sem login — o
 *  deploy pode chegar antes das variaveis sem rebentar nada. */
export const supabase: SupabaseClient | null =
  url && anonKey
    ? createClient(url, anonKey, {
        auth: { flowType: 'pkce', persistSession: true, detectSessionInUrl: true },
      })
    : null;
