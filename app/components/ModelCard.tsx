'use client';

import Link from 'next/link';

import { ScoreGauge } from '@/components/ScoreGauge';
import { categoryLabel, keywordLabel, useTranslation } from '@/lib/i18n';
import { TONE_TEXT, formatNumber, toneOf } from '@/lib/score';
import type { ModelSummary } from '@/lib/types';

export function ModelCard({ model }: { model: ModelSummary }) {
  const { t, locale } = useTranslation();
  const tone = toneOf(model.score);

  return (
    <Link
      href={`/models/${model.id}`}
      className="panel group flex flex-col gap-4 p-4 transition hover:border-open/50 hover:bg-panel"
    >
      <div className="flex items-start gap-3">
        <div className="min-w-0 flex-1">
          <h2 className="truncate text-[15px] font-medium text-slate-100">{model.name}</h2>
          <p className="mt-1 truncate font-mono text-xs text-muted">
            {keywordLabel(locale, model.keyword)}
          </p>
        </div>
        <ScoreGauge score={model.score} />
      </div>

      <div className="flex items-center gap-2">
        <span className="chip">{categoryLabel(locale, model.category)}</span>
        <span className={`font-mono text-[11px] uppercase tracking-wider ${TONE_TEXT[tone]}`}>
          {t(`tone.${tone}`)}
        </span>
      </div>

      <dl className="grid grid-cols-3 gap-2 border-t border-edge/70 pt-3 font-mono text-[11px]">
        <Metric label={t('metric.demand')} value={formatNumber(model.demand_norm)} />
        <Metric label={t('metric.competition')} value={formatNumber(model.competition_norm)} />
        <Metric label={t('metric.gap')} value={formatNumber(model.components.gap)} />
      </dl>
    </Link>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-muted">{label}</dt>
      <dd className="mt-0.5 text-slate-200">{value}</dd>
    </div>
  );
}
