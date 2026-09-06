'use client';

import { useCallback, useEffect, useState } from 'react';

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

async function getJson<T>(path: string): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, { headers: { Accept: 'application/json' } });
  } catch {
    throw { kind: 'network' } satisfies FetchError;
  }
  if (!response.ok) throw { kind: 'http', status: response.status } satisfies FetchError;
  return (await response.json()) as T;
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
