import { COMPONENT_HINT, COMPONENT_LABEL, TONE_HEX, toneOf } from '@/lib/score';
import type { ComponentKey, Parts } from '@/lib/types';

const ORDER: ComponentKey[] = ['gap', 'trend', 'margin'];

/** De onde vieram os pontos. Os pesos vivem so no Python: aqui mostram-se as
 *  contribuicoes ja calculadas, para nao haver duas fontes de verdade. */
export function Breakdown({ components, contributions }: { components: Parts; contributions: Parts }) {
  return (
    <dl className="space-y-4">
      {ORDER.map((key) => {
        const value = components[key];
        const points = contributions[key];
        return (
          <div key={key}>
            <div className="flex items-baseline justify-between gap-3">
              <dt className="text-sm text-slate-200">{COMPONENT_LABEL[key]}</dt>
              <dd className="font-mono text-xs text-muted">
                {value === undefined ? 'sem dados' : `${Math.round(value)}/100`}
                {points !== undefined && (
                  <span className="ml-2 text-slate-300">+{points.toFixed(1)} pts</span>
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
              {value === undefined
                ? 'Conector por ligar — o peso foi redistribuido pelos restantes.'
                : COMPONENT_HINT[key]}
            </p>
          </div>
        );
      })}
    </dl>
  );
}
