'use client';

import { useTranslation } from '@/lib/i18n';
import type { ModelSummary } from '@/lib/types';

const NEUTRAL = 50;

/** Explica um score achatado, em vez de deixar o painel parecer avariado.
 *
 *  Tudo aqui e derivado dos dados que chegaram, nunca de texto fixo: assim que
 *  um conector comecar a responder, ou houver um segundo dia de historico, o
 *  aviso desaparece sozinho — nao fica copy desatualizada para limpar depois. */
export function StatusNotice({ models }: { models: ModelSummary[] }) {
  const { t } = useTranslation();
  if (models.length === 0) return null;

  const missingGap = models.every((model) => model.components.gap === undefined);
  const flatTrend = models.every((model) => model.components.trend === NEUTRAL);
  if (!missingGap && !flatTrend) return null;

  const withDemand = models.filter((model) => model.demand_norm !== null).length;

  return (
    <div role="status" className="panel border-mid/30 bg-mid/5 px-4 py-3">
      <p className="font-mono text-[11px] uppercase tracking-wider text-mid">{t('notice.title')}</p>
      <ul className="mt-2 space-y-1 text-sm leading-relaxed text-muted">
        {missingGap && <li>{t('notice.no_competition')}</li>}
        {flatTrend && <li>{t('notice.no_history')}</li>}
      </ul>
      <p className="mt-2 font-mono text-[11px] text-muted">
        {t('notice.available', { withDemand, total: models.length })}
      </p>
    </div>
  );
}
