export type Tone = 'open' | 'mid' | 'tight';

/** Limiares de decisao: acima de 65 vale a pena imprimir, abaixo de 45 o mercado ja fechou.
 *  Os textos e traducoes de cada tom vivem em i18n.tsx (chave `tone.${tone}`).
 *  Espelham OPEN_THRESHOLD/SATURATED_THRESHOLD em core/scoring.py (Python) —
 *  os dois ficheiros nao partilham codigo, mudar um sem o outro desalinha o
 *  que se ve aqui do que o arquivamento automatico decide no backend. */
export const OPEN_MIN = 65;
export const MID_MIN = 45;

export function toneOf(score: number): Tone {
  if (score >= OPEN_MIN) return 'open';
  return score >= MID_MIN ? 'mid' : 'tight';
}

export const TONE_HEX: Record<Tone, string> = {
  open: '#22d3a5',
  mid: '#f2b544',
  tight: '#f2545b',
};

// Classes estaticas: o Tailwind so gera o que consegue ver no codigo.
export const TONE_TEXT: Record<Tone, string> = {
  open: 'text-open',
  mid: 'text-mid',
  tight: 'text-tight',
};

export function formatNumber(value: number | null | undefined, suffix = ''): string {
  return value === null || value === undefined ? '—' : `${Math.round(value)}${suffix}`;
}
