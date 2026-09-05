'use client';

import { useMemo, useState } from 'react';

import { Filters } from '@/components/Filters';
import { ModelCard } from '@/components/ModelCard';
import { EmptyState, ErrorState, LoadingGrid } from '@/components/StateView';
import { useJson } from '@/lib/api';
import type { ModelSummary, ModelsResponse } from '@/lib/types';

/** Os sinonimos entram na busca tal como na API: quem procura "kraken" tem de
 *  encontrar o polvo articulado. */
function haystack(model: ModelSummary): string {
  return [model.name, model.keyword, ...model.synonyms].join(' ').toLowerCase();
}

export default function Dashboard() {
  const { data, error, loading, reload } = useJson<ModelsResponse>('/api/models');
  const [query, setQuery] = useState('');
  const [category, setCategory] = useState<string | null>(null);

  // Filtragem no cliente: os dados ja vieram todos e assim nao ha ida ao servidor a cada tecla.
  const visible = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return (data?.models ?? []).filter(
      (model) =>
        (category === null || model.category === category) &&
        (needle === '' || haystack(model).includes(needle)),
    );
  }, [data, query, category]);

  return (
    <div className="space-y-6">
      <section className="space-y-2">
        <h1 className="text-xl font-semibold tracking-tight text-slate-50 sm:text-2xl">
          O que imprimir para vender
        </h1>
        <p className="max-w-2xl text-sm leading-relaxed text-muted">
          Ordenado por oportunidade: procura de compra a subir com o mercado ainda por fechar. Um
          modelo a bombar em atencao pontua baixo se a concorrencia ja o saturou.
        </p>
      </section>

      <Filters
        query={query}
        onQuery={setQuery}
        categories={data?.categories ?? []}
        active={category}
        onCategory={setCategory}
      />

      {loading && <LoadingGrid />}
      {!loading && error && <ErrorState message={error} onRetry={reload} />}
      {!loading && !error && visible.length === 0 && (
        <EmptyState
          message={
            (data?.models.length ?? 0) === 0
              ? 'Ainda nao ha snapshots. Corre a recolha diaria para popular o painel.'
              : 'Nenhum modelo corresponde a esta busca ou categoria.'
          }
        />
      )}
      {!loading && !error && visible.length > 0 && (
        <>
          <p aria-live="polite" className="font-mono text-[11px] text-muted">
            {visible.length} modelo{visible.length === 1 ? '' : 's'}
          </p>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {visible.map((model) => (
              <ModelCard key={model.id} model={model} />
            ))}
          </div>
        </>
      )}
    </div>
  );
}
