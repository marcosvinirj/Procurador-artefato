'use client';

import Link from 'next/link';

import { ScoreGauge } from '@/components/ScoreGauge';
import { categoryLabel, nameLabel, useTranslation } from '@/lib/i18n';
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
          <h2 className="text-[15px] font-medium leading-snug text-slate-100">
            {nameLabel(locale, model.name)}
          </h2>
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

/** Um produto do plano pago, visto do gratis. O servidor nao mandou nada dele:
 *  o que fica borrado e so decoracao, igual em todos os cartoes. */
export function LockedCard() {
  const { t } = useTranslation();
  const bar = 'h-2.5 rounded bg-slate-500/40';

  return (
    <div className="panel relative flex flex-col gap-4 overflow-hidden p-4">
      <div aria-hidden className="pointer-events-none flex select-none flex-col gap-4 blur-[3px]">
        <div className="flex items-start gap-3">
          <div className="flex-1 space-y-2 pt-1">
            <div className={`${bar} w-3/4`} />
            <div className={`${bar} w-1/2`} />
          </div>
          <div className="h-14 w-14 rounded-full border-4 border-open/60" />
        </div>
        <div className="flex gap-2">
          <div className={`${bar} w-16`} />
          <div className="h-2.5 w-20 rounded bg-open/40" />
        </div>
        <div className="grid grid-cols-3 gap-2 border-t border-edge/70 pt-3">
          {[0, 1, 2].map((index) => (
            <div key={index} className="space-y-1.5">
              <div className={`${bar} w-10`} />
              <div className={`${bar} w-6`} />
            </div>
          ))}
        </div>
      </div>
      <div className="absolute inset-0 flex items-center justify-center bg-ink/30">
        <span className="chip border-open/50 bg-ink/80 text-open">{t('locked.label')}</span>
      </div>
    </div>
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
