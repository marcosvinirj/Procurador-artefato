'use client';

import { useMemo, useState } from 'react';

import { Filters } from '@/components/Filters';
import { LockedCard, ModelCard } from '@/components/ModelCard';
import { RequireLogin } from '@/components/RequireLogin';
import { EmptyState, ErrorState, LoadingGrid } from '@/components/StateView';
import { StatusNotice } from '@/components/StatusNotice';
import { useJson } from '@/lib/api';
import { nameLabel, useTranslation, type Locale } from '@/lib/i18n';
import type { ModelSummary, ModelsResponse } from '@/lib/types';

/** Os sinonimos entram na busca tal como na API: quem procura "kraken" tem de
 *  encontrar o polvo articulado. O nome entra nas duas formas — a do idioma
 *  atual (o que a pessoa esta a ler) e a da base de dados. */
function haystack(model: ModelSummary, locale: Locale): string {
  return [nameLabel(locale, model.name), model.name, model.keyword, ...model.synonyms]
    .join(' ')
    .toLowerCase();
}

export default function Dashboard() {
  return (
    <RequireLogin>
      <Catalog />
    </RequireLogin>
  );
}

function Catalog() {
  const { t, locale } = useTranslation();
  const { data, error, loading, reload } = useJson<ModelsResponse>('/api/models');
  const [query, setQuery] = useState('');
  const [category, setCategory] = useState<string | null>(null);

  // Filtragem no cliente: os dados ja vieram todos e assim nao ha ida ao servidor a cada tecla.
  const visible = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return (data?.models ?? []).filter(
      (model) =>
        (category === null || model.category === category) &&
        (needle === '' || haystack(model, locale).includes(needle)),
    );
  }, [data, query, category, locale]);

  // Plano gratis: dos bloqueados so vem a categoria e a faixa do score. Uma
  // busca nunca os encontra (nao ha nome para comparar), por isso somem.
  const locked = data?.locked ?? [];
  const lockedShown =
    query.trim() !== '' ? [] : locked.filter((item) => category === null || item.category === category);
  const shown = visible.length + lockedShown.length;

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

      {!loading && !error && data && <StatusNotice models={data.models} />}
      {!loading && !error && data?.plan === 'free' && (
        <p className="font-mono text-[11px] text-open">
          {t('plan.free_notice', { shown: data.models.length, total: data.models.length + locked.length })}
        </p>
      )}

      {loading && <LoadingGrid />}
      {!loading && error && <ErrorState error={error} onRetry={reload} />}
      {!loading && !error && shown === 0 && (
        <EmptyState
          messageKey={
            (data?.models.length ?? 0) + locked.length === 0
              ? 'state.empty_no_snapshots'
              : 'state.empty_no_match'
          }
        />
      )}
      {!loading && !error && shown > 0 && (
        <>
          <p aria-live="polite" className="font-mono text-[11px] text-muted">
            {t(shown === 1 ? 'count.models.one' : 'count.models.other', { n: shown })}
          </p>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {visible.map((model) => (
              <ModelCard key={model.id} model={model} />
            ))}
            {lockedShown.map((item, index) => (
              <LockedCard key={`locked-${index}`} category={item.category} band={item.band} />
            ))}
          </div>
        </>
      )}
    </div>
  );
}
