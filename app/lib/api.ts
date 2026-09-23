'use client';

import { useCallback, useEffect, useState } from 'react';

import { supabase } from './supabase';

export interface FetchError {
  kind: 'http' | 'network';
  status?: number;
}

export interface Async<T> {
  data: T | null;
  error: FetchError | null;
  loading: boolean;
  reload: () => void;
}

/** Anexa o token da sessao quando existe. Qualquer falha a le-lo conta como
 *  anonimo: o login nunca pode impedir o catalogo de carregar. */
async function authHeader(): Promise<Record<string, string>> {
  try {
    const token = (await supabase?.auth.getSession())?.data.session?.access_token;
    return token ? { Authorization: `Bearer ${token}` } : {};
  } catch {
    return {};
  }
}

/** GET, ou POST com corpo JSON quando `body` vem definido; DELETE a pedido. O
 *  token vai no cabecalho (nunca em cookie), por isso outro site nao consegue
 *  forjar o pedido. */
async function request<T>(path: string, body?: unknown, method = body === undefined ? 'GET' : 'POST'): Promise<T> {
  const headers: Record<string, string> = { Accept: 'application/json', ...(await authHeader()) };
  const init: RequestInit = { headers, method };
  if (body !== undefined) {
    init.body = JSON.stringify(body);
    headers['Content-Type'] = 'application/json';
  }
  let response: Response;
  try {
    response = await fetch(path, init);
  } catch {
    throw { kind: 'network' } satisfies FetchError;
  }
  if (!response.ok) throw { kind: 'http', status: response.status } satisfies FetchError;
  return (await response.json()) as T;
}

export function getJson<T>(path: string): Promise<T> {
  return request<T>(path);
}

export function postJson<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, body);
}

export function deleteJson<T>(path: string): Promise<T> {
  return request<T>(path, undefined, 'DELETE');
}

function toFetchError(cause: unknown): FetchError {
  return cause && typeof cause === 'object' && 'kind' in cause ? (cause as FetchError) : { kind: 'network' };
}

/** Carrega JSON da nossa API mantendo os tres estados explicitos. O erro fica
 *  como dado estruturado (nao string) para ser traduzido no ponto de exibicao. */
export function useJson<T>(path: string): Async<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<FetchError | null>(null);
  const [loading, setLoading] = useState(true);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    getJson<T>(path)
      .then((result) => {
        if (!controller.signal.aborted) setData(result);
      })
      .catch((cause: unknown) => {
        if (!controller.signal.aborted) setError(toFetchError(cause));
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [path, attempt]);

  const reload = useCallback(() => setAttempt((n) => n + 1), []);
  return { data, error, loading, reload };
}
