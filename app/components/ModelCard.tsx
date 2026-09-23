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
        {model.showcase[0]?.image && (
          // eslint-disable-next-line @next/next/no-img-element -- imagem da Etsy, servida pelo CDN deles
          <img
            src={model.showcase[0].image}
            alt=""
            loading="lazy"
            referrerPolicy="no-referrer"
            className="h-14 w-14 shrink-0 rounded-lg border border-edge object-cover"
          />
        )}
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

/** Um produto do plano pago, visto do gratis. Do servidor so veio a categoria
 *  e a faixa do score (isso fica visivel, para despertar interesse); o nome e
 *  os numeros borrados sao texto de enfeite, iguais em todos os cartoes. */
export function LockedCard({ category, band }: { category: string; band: [number, number] }) {
  const { t, locale } = useTranslation();
  const tone = toneOf(band[0]);
  const hidden = 'pointer-events-none select-none blur-[5px]';

  return (
    <div className="panel flex flex-col gap-4 p-4">
      <div className="flex items-start gap-3">
        <div className="min-w-0 flex-1">
          <p aria-hidden className={`text-[15px] font-medium leading-snug text-slate-100 ${hidden}`}>
            Lorem ipsum dolor
          </p>
        </div>
        <ScoreGauge score={band[0]} range={band} />
      </div>

      <div className="flex items-center gap-2">
        <span className="chip">{categoryLabel(locale, category)}</span>
        <span className={`font-mono text-[11px] uppercase tracking-wider ${TONE_TEXT[tone]}`}>
          {t(`tone.${tone}`)}
        </span>
      </div>

      <div className="relative grid grid-cols-3 gap-2 border-t border-edge/70 pt-3 font-mono text-[11px]">
        {[t('metric.demand'), t('metric.competition'), t('metric.gap')].map((label) => (
          <div key={label}>
            <p className="text-muted">{label}</p>
            <p aria-hidden className={`mt-0.5 text-slate-200 ${hidden}`}>
              88
            </p>
          </div>
        ))}
        <span className="chip absolute bottom-0 right-0 border-open/50 bg-ink/90 text-open">
          {t('locked.label')}
        </span>
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
