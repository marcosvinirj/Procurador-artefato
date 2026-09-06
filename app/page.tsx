'use client';

import { useMemo, useState } from 'react';

import { Filters } from '@/components/Filters';
import { ModelCard } from '@/components/ModelCard';
import { EmptyState, ErrorState, LoadingGrid } from '@/components/StateView';
import { useJson } from '@/lib/api';
import { useTranslation } from '@/lib/i18n';
import type { ModelSummary, ModelsResponse } from '@/lib/types';

/** Os sinonimos entram na busca tal como na API: quem procura "kraken" tem de
 *  encontrar o polvo articulado. */
function haystack(model: ModelSummary): string {
  return [model.name, model.keyword, ...model.synonyms].join(' ').toLowerCase();
}

export default function Dashboard() {
  const { t } = useTranslation();
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
          {t('page.heading')}
        </h1>
        <p className="max-w-2xl text-sm leading-relaxed text-muted">{t('page.subtitle')}</p>
      </section>

      <Filters
        query={query}
        onQuery={setQuery}
        categories={data?.categories ?? []}
        active={category}
        onCategory={setCategory}
      />

      {loading && <LoadingGrid />}
      {!loading && error && <ErrorState error={error} onRetry={reload} />}
      {!loading && !error && visible.length === 0 && (
        <EmptyState
          messageKey={
            (data?.models.length ?? 0) === 0 ? 'state.empty_no_snapshots' : 'state.empty_no_match'
          }
        />
      )}
      {!loading && !error && visible.length > 0 && (
        <>
          <p aria-live="polite" className="font-mono text-[11px] text-muted">
            {t(visible.length === 1 ? 'count.models.one' : 'count.models.other', {
              n: visible.length,
            })}
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
