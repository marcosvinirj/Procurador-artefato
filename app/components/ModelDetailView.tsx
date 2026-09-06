'use client';

import Link from 'next/link';

import { Breakdown } from '@/components/Breakdown';
import { ScoreGauge } from '@/components/ScoreGauge';
import { ErrorState, LoadingGrid } from '@/components/StateView';
import { TrendChart } from '@/components/TrendChart';
import { useJson } from '@/lib/api';
import { categoryLabel, nameLabel, useTranslation } from '@/lib/i18n';
import { TONE_TEXT, formatNumber, toneOf } from '@/lib/score';
import type { ModelDetail } from '@/lib/types';

export function ModelDetailView({ id }: { id: string }) {
  const { t } = useTranslation();
  const { data, error, loading, reload } = useJson<ModelDetail>(`/api/models/${id}`);

  return (
    <div className="space-y-6">
      <Link
        href="/"
        className="inline-flex rounded font-mono text-xs uppercase tracking-wider text-muted transition hover:text-open"
      >
        {t('detail.back')}
      </Link>

      {loading && <LoadingGrid />}
      {!loading && error && <ErrorState error={error} onRetry={reload} />}
      {!loading && !error && data && <Detail model={data} />}
    </div>
  );
}

function Detail({ model }: { model: ModelDetail }) {
  const { t, locale } = useTranslation();
  const tone = toneOf(model.score);

  return (
    <>
      <section className="panel flex flex-col gap-4 p-5 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0">
          <h1 className="text-xl font-semibold tracking-tight text-slate-50">
            {nameLabel(locale, model.name)}
          </h1>
          <span className="chip mt-3 inline-block">{categoryLabel(locale, model.category)}</span>

          {/* Termos de mercado ficam em ingles de proposito: e o que se escreve
              no Etsy, e e por eles que a recolha mede procura e concorrencia. */}
          <div className="mt-4">
            <p className="font-mono text-[10px] uppercase tracking-wider text-muted">
              {t('detail.market_terms')}
            </p>
            <div className="mt-1.5 flex flex-wrap gap-2">
              <span className="chip border-open/40 text-slate-200">{model.keyword}</span>
              {model.synonyms.map((synonym) => (
                <span key={synonym} className="chip">
                  {synonym}
                </span>
              ))}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-4 sm:flex-col sm:items-end sm:gap-1">
          <ScoreGauge score={model.score} large />
          <span className={`font-mono text-xs uppercase tracking-wider ${TONE_TEXT[tone]}`}>
            {t(`tone.${tone}`)}
          </span>
        </div>
      </section>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <section className="panel p-5">
          <h2 className="font-mono text-xs uppercase tracking-wider text-muted">
            {t('detail.demand_vs_competition')}
          </h2>
          <div className="mt-4">
            <TrendChart history={model.history} />
          </div>
          <dl className="mt-4 grid grid-cols-3 gap-3 border-t border-edge/70 pt-4 font-mono text-[11px]">
            <Stat label={t('metric.demand')} value={formatNumber(model.demand_norm)} />
            <Stat label={t('stat.competition_full')} value={formatNumber(model.competition_norm)} />
            <Stat label={t('stat.updated')} value={model.updated_at ?? '—'} />
          </dl>
        </section>

        <section className="panel p-5">
          <h2 className="font-mono text-xs uppercase tracking-wider text-muted">
            {t('detail.score_breakdown')}
          </h2>
          <div className="mt-4">
            <Breakdown components={model.components} contributions={model.contributions} />
          </div>
        </section>
      </div>
    </>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-muted">{label}</dt>
      <dd className="mt-0.5 truncate text-slate-200">{value}</dd>
    </div>
  );
}
