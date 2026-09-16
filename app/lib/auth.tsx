'use client';

import type { Session, SupabaseClient } from '@supabase/supabase-js';
import { createContext, useContext, useEffect, useMemo, useState } from 'react';

import { getJson } from './api';
import { supabase } from './supabase';

/** O erro vai como codigo do Supabase (traduzido no ecra), nunca como a
 *  mensagem crua, que so existe em ingles. */
export type AuthResult = { ok: true } | { ok: false; code: string };

async function run(
  action: (client: SupabaseClient) => Promise<{ error: { code?: string } | null }>,
): Promise<AuthResult> {
  if (!supabase) return { ok: false, code: 'unavailable' };
  try {
    const { error } = await action(supabase);
    return error ? { ok: false, code: error.code ?? 'unknown' } : { ok: true };
  } catch {
    return { ok: false, code: 'unknown' };
  }
}

/** Os links de email voltam sempre ao nosso dominio; o Supabase so aceita
 *  destinos do mesmo dominio do Site URL ou da lista de Redirect URLs. */
const back = (path: string) => `${window.location.origin}${path}`;

// A senha vai direto do browser para o Supabase: nunca passa pela nossa API.
const actions = {
  signUp: (email: string, password: string) =>
    run((c) => c.auth.signUp({ email, password, options: { emailRedirectTo: back('/login') } })),
  signIn: (email: string, password: string) =>
    run((c) => c.auth.signInWithPassword({ email, password })),
  resendConfirmation: (email: string) =>
    run((c) => c.auth.resend({ type: 'signup', email, options: { emailRedirectTo: back('/login') } })),
  requestReset: (email: string) =>
    run((c) => c.auth.resetPasswordForEmail(email, { redirectTo: back('/login/reset') })),
  updatePassword: (password: string) => run((c) => c.auth.updateUser({ password })),
  signOut: async () => {
    await supabase?.auth.signOut();
  },
};

interface AuthValue extends Readonly<typeof actions> {
  /** false quando o login nao esta configurado neste deploy. */
  available: boolean;
  /** false ate se saber se ha sessao: evita mostrar as boas-vindas a quem ja entrou. */
  ready: boolean;
  session: Session | null;
  /** So decide se o link "Admin" aparece; quem manda e o servidor, a cada pedido. */
  isAdmin: boolean;
}

const AuthContext = createContext<AuthValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [ready, setReady] = useState(supabase === null);

  useEffect(() => {
    if (!supabase) return;
    // getSession espera pela troca do codigo quando se chega de um link de email.
    supabase.auth
      .getSession()
      .then(({ data }) => setSession(data.session))
      .catch(() => setSession(null))
      .finally(() => setReady(true));
    const { data } = supabase.auth.onAuthStateChange((_event, next) => setSession(next));
    return () => data.subscription.unsubscribe();
  }, []);

  const [isAdmin, setIsAdmin] = useState(false);
  const userId = session?.user.id;
  useEffect(() => {
    setIsAdmin(false);
    if (!userId) return;
    let live = true;
    getJson<{ is_admin?: boolean }>('/api/me')
      .then((me) => live && setIsAdmin(me.is_admin === true))
      .catch(() => undefined);
    return () => {
      live = false;
    };
  }, [userId]);

  const value = useMemo<AuthValue>(
    () => ({ ...actions, available: supabase !== null, ready, session, isAdmin }),
    [ready, session, isAdmin],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth deve ser usado dentro de AuthProvider');
  return ctx;
}
