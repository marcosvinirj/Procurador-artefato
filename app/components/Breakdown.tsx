'use client';

import { useTranslation } from '@/lib/i18n';
import { TONE_HEX, toneOf } from '@/lib/score';
import type { ComponentKey, Parts } from '@/lib/types';

const ORDER: ComponentKey[] = ['gap', 'trend', 'margin'];

const KEYS: Record<ComponentKey, { label: string; hint: string }> = {
  gap: { label: 'component.gap.label', hint: 'component.gap.hint' },
  trend: { label: 'component.trend.label', hint: 'component.trend.hint' },
  margin: { label: 'component.margin.label', hint: 'component.margin.hint' },
};

/** De onde vieram os pontos. Os pesos vivem so no Python: aqui mostram-se as
 *  contribuicoes ja calculadas, para nao haver duas fontes de verdade. */
export function Breakdown({ components, contributions }: { components: Parts; contributions: Parts }) {
  const { t } = useTranslation();

  return (
    <dl className="space-y-4">
      {ORDER.map((key) => {
        const value = components[key];
        const points = contributions[key];
        return (
          <div key={key}>
            <div className="flex items-baseline justify-between gap-3">
              <dt className="text-sm text-slate-200">{t(KEYS[key].label)}</dt>
              <dd className="font-mono text-xs text-muted">
                {value === undefined ? t('breakdown.no_data') : `${Math.round(value)}/100`}
                {points !== undefined && (
                  <span className="ml-2 text-slate-300">
                    +{points.toFixed(1)} {t('breakdown.points_suffix')}
                  </span>
                )}
              </dd>
            </div>
            <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-edge">
              {value !== undefined && (
                <div
                  className="h-full rounded-full"
                  style={{ width: `${value}%`, backgroundColor: TONE_HEX[toneOf(value)] }}
                />
              )}
            </div>
            <p className="mt-1.5 text-xs text-muted">
              {value === undefined ? t('breakdown.pending_connector') : t(KEYS[key].hint)}
            </p>
          </div>
        );
      })}
    </dl>
  );
}
