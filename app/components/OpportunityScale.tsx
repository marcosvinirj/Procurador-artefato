'use client';

import { useId } from 'react';

import { useTranslation } from '@/lib/i18n';
import { MID_MIN, OPEN_MIN, TONE_HEX, type Tone } from '@/lib/score';

const CX = 100;
const CY = 100;
const RADIUS = 78;
const NEEDLE_AT = 82; // so ilustra a leitura: nao e o score de nenhum produto

/** Ponto do semicirculo para um score 0–100 (0 a esquerda, 100 a direita). */
function point(score: number, radius = RADIUS): [number, number] {
  const angle = Math.PI * (1 - score / 100);
  return [CX + radius * Math.cos(angle), CY - radius * Math.sin(angle)];
}

function arc(from: number, to: number): string {
  const [x1, y1] = point(from);
  const [x2, y2] = point(to);
  return `M ${x1.toFixed(2)} ${y1.toFixed(2)} A ${RADIUS} ${RADIUS} 0 0 1 ${x2.toFixed(2)} ${y2.toFixed(2)}`;
}

// As faixas sao os limiares reais de toneOf: a legenda nao inventa nada.
const ZONES: { tone: Tone; from: number; to: number; range: string }[] = [
  { tone: 'tight', from: 0, to: MID_MIN, range: `0–${MID_MIN - 1}` },
  { tone: 'mid', from: MID_MIN, to: OPEN_MIN, range: `${MID_MIN}–${OPEN_MIN - 1}` },
  { tone: 'open', from: OPEN_MIN, to: 100, range: `${OPEN_MIN}–100` },
];
const GAP = 0.9;

/** O medidor do produto em ponto grande, com textura de camadas de impressao
 *  FDM; ao carregar, "imprime-se" de baixo para cima. */
export function OpportunityScale({ large = false }: { large?: boolean }) {
  const { t } = useTranslation();
  const mask = `layers-${useId().replace(/[^a-zA-Z0-9]/g, '')}`;
  const [nx, ny] = point(NEEDLE_AT, RADIUS - 20);

  return (
    <figure className="flex w-full flex-col items-center gap-5">
      <svg viewBox="0 0 200 110" className={`print-in ${large ? 'w-72 sm:w-96' : 'w-64 sm:w-72'}`} aria-hidden>
        <defs>
          {/* y=0.6: uma camada comeca logo acima do topo do arco (y=11), senao o
              topo sai achatado e parece cortado. */}
          <pattern id={`${mask}-p`} y="0.6" width="200" height="3.4" patternUnits="userSpaceOnUse">
            <rect width="200" height="2.5" fill="#fff" />
          </pattern>
          <mask id={mask}>
            <rect width="200" height="110" fill={`url(#${mask}-p)`} />
          </mask>
        </defs>
        <g mask={`url(#${mask})`} fill="none" strokeWidth="22">
          {ZONES.map((zone) => (
            <path
              key={zone.tone}
              d={arc(zone.from + (zone.from > 0 ? GAP : 0), zone.to - (zone.to < 100 ? GAP : 0))}
              stroke={TONE_HEX[zone.tone]}
            />
          ))}
        </g>
        <g className="needle-in">
          <line x1={CX} y1={CY} x2={nx} y2={ny} stroke="#e2e8f0" strokeWidth="3" strokeLinecap="round" />
          <circle cx={CX} cy={CY} r="5.5" fill="#e2e8f0" />
        </g>
      </svg>

      <figcaption className="w-full max-w-sm">
        <p className="text-center font-mono text-[11px] uppercase tracking-[0.18em] text-muted">
          {t('scale.title')}
        </p>
        <ul className="mt-3 grid grid-cols-3 gap-3 text-center">
          {ZONES.map((zone) => (
            <li key={zone.tone} className="space-y-1.5">
              <span className="mx-auto block h-1 w-8 rounded-full" style={{ backgroundColor: TONE_HEX[zone.tone] }} />
              <span className="block text-xs leading-tight text-slate-200">{t(`tone.${zone.tone}`)}</span>
              <span className="block font-mono text-[11px] text-muted">{zone.range}</span>
            </li>
          ))}
        </ul>
      </figcaption>
    </figure>
  );
}
