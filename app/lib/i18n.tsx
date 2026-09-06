'use client';

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';

export type Locale = 'en' | 'pt' | 'es';
export const LOCALES: Locale[] = ['en', 'pt', 'es'];
export const LOCALE_LABEL: Record<Locale, string> = { en: 'EN', pt: 'PT', es: 'ES' };

const DEFAULT_LOCALE: Locale = 'en';
const STORAGE_KEY = 'trendprint.locale';

type Dict = Record<string, string>;

const en: Dict = {
  'meta.title': 'TrendPrint — what to print to sell',
  'header.tagline': 'high demand · low competition',
  'header.language_label': 'Language',
  'page.heading': 'What to print to sell',
  'page.subtitle':
    'Ranked by opportunity: buying demand rising while the market is still open. A model spiking in attention still scores low once competition has saturated it.',
  'filters.search': 'Search model or keyword…',
  'filters.all': 'all',
  'filters.category_aria': 'Filter by category',
  'state.loading': 'Loading opportunities…',
  'state.empty_title': 'No results',
  'state.empty_no_snapshots': 'No snapshots yet. Run the daily collection to populate the dashboard.',
  'state.empty_no_match': 'No model matches this search or category.',
  'state.error_title': 'Failed to load',
  'state.retry': 'Try again',
  'error.http': 'The API responded with {{status}}.',
  'error.network': 'Could not reach the API.',
  'count.models.one': '{{n}} model',
  'count.models.other': '{{n}} models',
  'metric.demand': 'demand',
  'metric.competition': 'comp.',
  'metric.gap': 'gap',
  'tone.open': 'Open market',
  'tone.mid': 'Contested',
  'tone.tight': 'Saturated',
  'gauge.aria': 'Opportunity score {{score}} out of 100 — {{tone}}',
  'detail.back': '← back',
  'detail.demand_vs_competition': 'Demand vs. competition',
  'detail.score_breakdown': 'Score breakdown',
  'stat.competition_full': 'competition',
  'stat.updated': 'updated',
  'component.gap.label': 'Opportunity gap',
  'component.gap.hint': 'Demand minus competition, within the category',
  'component.trend.label': 'Demand direction',
  'component.trend.hint': 'Change in demand vs. 7 days before',
  'component.margin.label': 'Estimated margin',
  'component.margin.hint': 'Price on top listings',
  'breakdown.no_data': 'no data',
  'breakdown.pending_connector': 'Connector not yet linked — its weight was redistributed to the others.',
  'breakdown.points_suffix': 'pts',
  'chart.no_history': 'Not enough history yet. Daily collection adds one point per day.',
  'chart.legend_demand': '— demand',
  'chart.legend_competition': '--- competition',
  'chart.legend_independent_scales': 'independent scales',
  'chart.aria': 'Demand and competition evolution over {{days}} days',
};

const pt: Dict = {
  'meta.title': 'TrendPrint — o que imprimir para vender',
  'header.tagline': 'procura alta · concorrência baixa',
  'header.language_label': 'Idioma',
  'page.heading': 'O que imprimir para vender',
  'page.subtitle':
    'Ordenado por oportunidade: procura de compra em alta com o mercado ainda aberto. Um modelo em alta de atenção ainda pontua baixo se a concorrência já o saturou.',
  'filters.search': 'Procurar modelo ou palavra-chave…',
  'filters.all': 'todas',
  'filters.category_aria': 'Filtrar por categoria',
  'state.loading': 'A carregar oportunidades…',
  'state.empty_title': 'Sem resultados',
  'state.empty_no_snapshots': 'Ainda não há snapshots. Corre a recolha diária para popular o painel.',
  'state.empty_no_match': 'Nenhum modelo corresponde a esta busca ou categoria.',
  'state.error_title': 'Falha ao carregar',
  'state.retry': 'Tentar de novo',
  'error.http': 'A API respondeu {{status}}.',
  'error.network': 'Não foi possível contactar a API.',
  'count.models.one': '{{n}} modelo',
  'count.models.other': '{{n}} modelos',
  'metric.demand': 'procura',
  'metric.competition': 'concorr.',
  'metric.gap': 'gap',
  'tone.open': 'Mercado aberto',
  'tone.mid': 'Disputado',
  'tone.tight': 'Saturado',
  'gauge.aria': 'Score de oportunidade {{score}} em 100 — {{tone}}',
  'detail.back': '← voltar',
  'detail.demand_vs_competition': 'Procura vs. concorrência',
  'detail.score_breakdown': 'Decomposição do score',
  'stat.competition_full': 'concorrência',
  'stat.updated': 'atualizado',
  'component.gap.label': 'Gap de oportunidade',
  'component.gap.hint': 'Procura menos concorrência, dentro da categoria',
  'component.trend.label': 'Direção da procura',
  'component.trend.hint': 'Variação da procura vs. 7 dias antes',
  'component.margin.label': 'Margem estimada',
  'component.margin.hint': 'Preço praticado nas listagens de topo',
  'breakdown.no_data': 'sem dados',
  'breakdown.pending_connector': 'Conector por ligar — o peso foi redistribuído pelos restantes.',
  'breakdown.points_suffix': 'pts',
  'chart.no_history': 'Ainda sem histórico suficiente. A recolha diária acumula um ponto por dia.',
  'chart.legend_demand': '— procura',
  'chart.legend_competition': '--- concorrência',
  'chart.legend_independent_scales': 'escalas independentes',
  'chart.aria': 'Evolução de procura e concorrência ao longo de {{days}} dias',
};

const es: Dict = {
  'meta.title': 'TrendPrint — qué imprimir para vender',
  'header.tagline': 'alta demanda · baja competencia',
  'header.language_label': 'Idioma',
  'page.heading': 'Qué imprimir para vender',
  'page.subtitle':
    'Ordenado por oportunidad: demanda de compra en alza con el mercado aún abierto. Un modelo con atención en alza aún puntúa bajo si la competencia ya lo saturó.',
  'filters.search': 'Buscar modelo o palabra clave…',
  'filters.all': 'todas',
  'filters.category_aria': 'Filtrar por categoría',
  'state.loading': 'Cargando oportunidades…',
  'state.empty_title': 'Sin resultados',
  'state.empty_no_snapshots': 'Aún no hay snapshots. Ejecuta la recolección diaria para poblar el panel.',
  'state.empty_no_match': 'Ningún modelo coincide con esta búsqueda o categoría.',
  'state.error_title': 'Error al cargar',
  'state.retry': 'Reintentar',
  'error.http': 'La API respondió {{status}}.',
  'error.network': 'No se pudo contactar la API.',
  'count.models.one': '{{n}} modelo',
  'count.models.other': '{{n}} modelos',
  'metric.demand': 'demanda',
  'metric.competition': 'compet.',
  'metric.gap': 'gap',
  'tone.open': 'Mercado abierto',
  'tone.mid': 'Disputado',
  'tone.tight': 'Saturado',
  'gauge.aria': 'Puntaje de oportunidad {{score}} de 100 — {{tone}}',
  'detail.back': '← volver',
  'detail.demand_vs_competition': 'Demanda vs. competencia',
  'detail.score_breakdown': 'Desglose del puntaje',
  'stat.competition_full': 'competencia',
  'stat.updated': 'actualizado',
  'component.gap.label': 'Brecha de oportunidad',
  'component.gap.hint': 'Demanda menos competencia, dentro de la categoría',
  'component.trend.label': 'Dirección de la demanda',
  'component.trend.hint': 'Variación de la demanda vs. 7 días antes',
  'component.margin.label': 'Margen estimado',
  'component.margin.hint': 'Precio en los listados principales',
  'breakdown.no_data': 'sin datos',
  'breakdown.pending_connector': 'Conector aún no vinculado — su peso se redistribuyó entre los demás.',
  'breakdown.points_suffix': 'pts',
  'chart.no_history': 'Aún sin historial suficiente. La recolección diaria agrega un punto por día.',
  'chart.legend_demand': '— demanda',
  'chart.legend_competition': '--- competencia',
  'chart.legend_independent_scales': 'escalas independientes',
  'chart.aria': 'Evolución de demanda y competencia durante {{days}} días',
};

const DICTS: Record<Locale, Dict> = { en, pt, es };

/** So os 4 slugs fixos do seed. Uma categoria desconhecida cai no proprio slug
 *  em vez de rebentar — mesma filosofia do backend: nunca inventar, nunca falhar. */
export const CATEGORY_LABEL: Record<Locale, Dict> = {
  en: { brinquedos: 'Toys', decoracao: 'Decor', gadgets: 'Gadgets', utilidades: 'Utilities' },
  pt: { brinquedos: 'Brinquedos', decoracao: 'Decoração', gadgets: 'Gadgets', utilidades: 'Utilidades' },
  es: { brinquedos: 'Juguetes', decoracao: 'Decoración', gadgets: 'Gadgets', utilidades: 'Utilidades' },
};

export function categoryLabel(locale: Locale, raw: string): string {
  return CATEGORY_LABEL[locale][raw] ?? raw;
}

/** So para exibicao — o `keyword` guardado e usado na recolha (Etsy/Google
 *  Trends) continua sempre em ingles, e e esse valor que fica no dataset.
 *  Um keyword novo, sem traducao ainda, cai no proprio texto em ingles. */
const KEYWORD_LABEL: Record<Locale, Dict> = {
  en: {},
  pt: {
    'articulated octopus': 'polvo articulado',
    'articulated dragon': 'dragão articulado',
    'flexi axolotl': 'axolote flexível',
    'articulated snake': 'cobra articulada',
    'fidget slider': 'slider fidget',
    'infinity cube': 'cubo infinito',
    'flexi shark': 'tubarão flexível',
    'spiral vase': 'vaso espiral',
    'moon lamp': 'luminária lua',
    lithophane: 'litofania',
    'face planter': 'vaso rosto',
    'geometric wall art': 'arte geométrica de parede',
    'nativity set': 'presépio',
    'headphone stand': 'suporte de fones',
    'cable organizer': 'organizador de cabos',
    'phone stand': 'suporte de telemóvel',
    'stackable storage bin': 'caixa empilhável',
    'jar opener': 'abridor de potes',
    'toilet paper holder': 'porta papel higiénico',
    'key holder wall': 'porta-chaves de parede',
    'switch dock': 'dock para switch',
    'controller holder': 'suporte de comando',
    'laptop stand': 'suporte de portátil',
    'desk organizer': 'organizador de secretária',
    'earbud case': 'estojo de fones',
  },
  es: {
    'articulated octopus': 'pulpo articulado',
    'articulated dragon': 'dragón articulado',
    'flexi axolotl': 'ajolote flexible',
    'articulated snake': 'serpiente articulada',
    'fidget slider': 'slider fidget',
    'infinity cube': 'cubo infinito',
    'flexi shark': 'tiburón flexible',
    'spiral vase': 'jarrón espiral',
    'moon lamp': 'lámpara de luna',
    lithophane: 'litofanía',
    'face planter': 'maceta con rostro',
    'geometric wall art': 'arte geométrico de pared',
    'nativity set': 'nacimiento',
    'headphone stand': 'soporte de auriculares',
    'cable organizer': 'organizador de cables',
    'phone stand': 'soporte de teléfono',
    'stackable storage bin': 'caja apilable',
    'jar opener': 'abridor de frascos',
    'toilet paper holder': 'portarrollos',
    'key holder wall': 'llavero de pared',
    'switch dock': 'dock para switch',
    'controller holder': 'soporte de mando',
    'laptop stand': 'soporte de portátil',
    'desk organizer': 'organizador de escritorio',
    'earbud case': 'estuche de auriculares',
  },
};

export function keywordLabel(locale: Locale, raw: string): string {
  return KEYWORD_LABEL[locale][raw] ?? raw;
}

interface LanguageContextValue {
  locale: Locale;
  setLocale: (next: Locale) => void;
  t: (key: string, vars?: Record<string, string | number>) => string;
}

const LanguageContext = createContext<LanguageContextValue | null>(null);

export function LanguageProvider({ children }: { children: React.ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>(DEFAULT_LOCALE);

  // Le a preferencia guardada so no cliente, depois do primeiro render, para o
  // HTML do servidor (sempre "en") e a primeira pintura no browser baterem certo.
  useEffect(() => {
    try {
      const saved = window.localStorage.getItem(STORAGE_KEY);
      if (saved && (LOCALES as string[]).includes(saved)) setLocaleState(saved as Locale);
    } catch {
      // localStorage indisponivel (janela privada, etc.): fica no idioma por omissao
    }
  }, []);

  // So o lang do <html> (acessibilidade). O titulo da aba fica com o Next.js:
  // escrever document.title aqui competia com a gestao propria dele apos um
  // reload completo (o Next reafirma a <title> da metadata por cima), dando
  // um resultado inconsistente sem ganho real.
  useEffect(() => {
    document.documentElement.lang = locale;
  }, [locale]);

  const setLocale = useCallback((next: Locale) => {
    setLocaleState(next);
    try {
      window.localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // preferencia e so de conveniencia; falhar aqui nao pode quebrar a troca
    }
  }, []);

  const t = useCallback(
    (key: string, vars?: Record<string, string | number>) => {
      let text = DICTS[locale][key] ?? DICTS.en[key] ?? key;
      if (vars) {
        for (const [name, value] of Object.entries(vars)) {
          text = text.replaceAll(`{{${name}}}`, String(value));
        }
      }
      return text;
    },
    [locale],
  );

  const value = useMemo(() => ({ locale, setLocale, t }), [locale, setLocale, t]);
  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>;
}

export function useTranslation(): LanguageContextValue {
  const ctx = useContext(LanguageContext);
  if (!ctx) throw new Error('useTranslation deve ser usado dentro de LanguageProvider');
  return ctx;
}
