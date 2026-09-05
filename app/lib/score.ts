import type { ComponentKey } from './types';

export type Tone = 'open' | 'mid' | 'tight';

/** Limiares de decisao: acima de 65 vale a pena imprimir, abaixo de 45 o mercado ja fechou. */
export function toneOf(score: number): Tone {
  if (score >= 65) return 'open';
  return score >= 45 ? 'mid' : 'tight';
}

export const TONE_LABEL: Record<Tone, string> = {
  open: 'Mercado aberto',
  mid: 'Disputado',
  tight: 'Saturado',
};

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

export const COMPONENT_LABEL: Record<ComponentKey, string> = {
  gap: 'Gap de oportunidade',
  trend: 'Direcao da procura',
  margin: 'Margem estimada',
};

export const COMPONENT_HINT: Record<ComponentKey, string> = {
  gap: 'Procura menos concorrencia, dentro da categoria',
  trend: 'Variacao da procura vs. 7 dias antes',
  margin: 'Preco praticado nas listagens de topo',
};

export function formatNumber(value: number | null | undefined, suffix = ''): string {
  return value === null || value === undefined ? '—' : `${Math.round(value)}${suffix}`;
}
