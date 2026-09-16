'use client';

import { useTranslation } from '@/lib/i18n';
import { TONE_HEX, toneOf } from '@/lib/score';

const RADIUS = 42;
const ARC = Math.PI * RADIUS;

/** Medidor semicircular: a cor comunica a decisao antes de se ler o numero.
 *  Com `range` (produto bloqueado no plano gratis) mostra so o troco do arco
 *  entre os dois limites e a faixa em texto, nunca o score exato. */
export function ScoreGauge({
  score,
  large = false,
  range,
}: {
  score: number;
  large?: boolean;
  range?: [number, number];
}) {
  const { t } = useTranslation();
  const tone = toneOf(score);
  const clamped = Math.max(0, Math.min(100, score));
  const dash = range
    ? { strokeDasharray: `${(ARC * (range[1] - range[0])) / 100} ${ARC}`, strokeDashoffset: (-ARC * range[0]) / 100 }
    : { strokeDasharray: ARC, strokeDashoffset: ARC * (1 - clamped / 100) };
  const label = range ? `${range[0]}–${range[1]}` : String(Math.round(score));

  return (
    <svg
      viewBox="0 0 100 58"
      className={large ? 'h-24 w-40' : 'h-14 w-24'}
      role="img"
      aria-label={
        range
          ? t('gauge.aria_range', { low: range[0], high: range[1], tone: t(`tone.${tone}`) })
          : t('gauge.aria', { score: Math.round(score), tone: t(`tone.${tone}`) })
      }
    >
      <path
        d="M 8 50 A 42 42 0 0 1 92 50"
        fill="none"
        stroke="#1e2934"
        strokeWidth="8"
        strokeLinecap="round"
      />
      <path
        d="M 8 50 A 42 42 0 0 1 92 50"
        fill="none"
        stroke={TONE_HEX[tone]}
        strokeWidth="8"
        strokeLinecap="round"
        {...dash}
      />
      <text
        x="50"
        y="47"
        textAnchor="middle"
        fill={TONE_HEX[tone]}
        className={`font-mono font-semibold ${range ? 'text-[16px]' : large ? 'text-[22px]' : 'text-[20px]'}`}
      >
        {label}
      </text>
    </svg>
  );
}
