'use client';

import { useTranslation } from '@/lib/i18n';
import { TONE_HEX, toneOf } from '@/lib/score';

const RADIUS = 42;
const ARC = Math.PI * RADIUS;

/** Medidor semicircular: a cor comunica a decisao antes de se ler o numero. */
export function ScoreGauge({ score, large = false }: { score: number; large?: boolean }) {
  const { t } = useTranslation();
  const tone = toneOf(score);
  const clamped = Math.max(0, Math.min(100, score));

  return (
    <svg
      viewBox="0 0 100 58"
      className={large ? 'h-24 w-40' : 'h-14 w-24'}
      role="img"
      aria-label={t('gauge.aria', { score: Math.round(score), tone: t(`tone.${tone}`) })}
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
        strokeDasharray={ARC}
        strokeDashoffset={ARC * (1 - clamped / 100)}
      />
      <text
        x="50"
        y="47"
        textAnchor="middle"
        fill={TONE_HEX[tone]}
        className={`font-mono font-semibold ${large ? 'text-[22px]' : 'text-[20px]'}`}
      >
        {Math.round(score)}
      </text>
    </svg>
  );
}
