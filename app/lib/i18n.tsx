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
  'notice.title': 'incomplete score',
  'notice.no_competition': 'No competition source is connected yet, so the opportunity gap (60% of the score) and the margin (15%) cannot be computed. Every model sits at the neutral 50.',
  'notice.no_history': 'Demand direction needs a second day of collection before it can tell the models apart.',
  'notice.available': '{{withDemand}} of {{total}} models have demand data.',
  'metric.demand': 'demand',
  'metric.competition': 'comp.',
  'metric.gap': 'gap',
  'tone.open': 'Open market',
  'tone.mid': 'Contested',
  'tone.tight': 'Saturated',
  'gauge.aria': 'Opportunity score {{score}} out of 100 — {{tone}}',
  'detail.back': '← back',
  'detail.market_terms': 'market terms',
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
    'Ordenado por oportunidade: procura de compra em alta com o mercado ainda aberto. Um modelo com a atenção em alta ainda pontua baixo se a concorrência já o saturou.',
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
  'notice.title': 'score incompleto',
  'notice.no_competition': 'Ainda não há fonte de concorrência ligada, por isso o gap de oportunidade (60% do score) e a margem (15%) não podem ser calculados. Todos os modelos ficam no valor neutro 50.',
  'notice.no_history': 'A direção da procura precisa de um segundo dia de recolha para conseguir distinguir os modelos.',
  'notice.available': '{{withDemand}} de {{total}} modelos têm dados de procura.',
  'metric.demand': 'procura',
  'metric.competition': 'concorr.',
  'metric.gap': 'gap',
  'tone.open': 'Mercado aberto',
  'tone.mid': 'Disputado',
  'tone.tight': 'Saturado',
  'gauge.aria': 'Score de oportunidade {{score}} em 100 — {{tone}}',
  'detail.back': '← voltar',
  'detail.market_terms': 'termos de mercado',
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
  'notice.title': 'puntaje incompleto',
  'notice.no_competition': 'Aún no hay fuente de competencia conectada, así que la brecha de oportunidad (60% del puntaje) y el margen (15%) no se pueden calcular. Todos los modelos quedan en el valor neutro 50.',
  'notice.no_history': 'La dirección de la demanda necesita un segundo día de recolección para poder distinguir los modelos.',
  'notice.available': '{{withDemand}} de {{total}} modelos tienen datos de demanda.',
  'metric.demand': 'demanda',
  'metric.competition': 'compet.',
  'metric.gap': 'gap',
  'tone.open': 'Mercado abierto',
  'tone.mid': 'Disputado',
  'tone.tight': 'Saturado',
  'gauge.aria': 'Puntaje de oportunidad {{score}} de 100 — {{tone}}',
  'detail.back': '← volver',
  'detail.market_terms': 'términos de mercado',
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
  en: { brinquedos: 'Toys', decoracao: 'Decor', gadgets: 'Tech', utilidades: 'Utilities' },
  pt: { brinquedos: 'Brinquedos', decoracao: 'Decoração', gadgets: 'Tech', utilidades: 'Utilidades' },
  es: { brinquedos: 'Juguetes', decoracao: 'Decoración', gadgets: 'Tech', utilidades: 'Utilidades' },
};

export function categoryLabel(locale: Locale, raw: string): string {
  return CATEGORY_LABEL[locale][raw] ?? raw;
}

/** Nome do produto por idioma, indexado pelo `name` que vem do Supabase.
 *  O dataset guarda um so nome (pt, sem acentos); aqui ele ganha a forma
 *  correta em cada lingua — incluindo o proprio pt, com os acentos que
 *  faltavam. Um modelo novo, ainda sem traducao, cai no nome da base de dados.
 *
 *  O `keyword` NAO se traduz: e o termo real de pesquisa no Etsy/Google Trends,
 *  e e como termo de mercado que ele aparece na pagina de detalhe. */
const NAME_LABEL: Record<Locale, Dict> = {
  en: {
    'Polvo Articulado': 'Articulated Octopus',
    'Dragao Articulado': 'Articulated Dragon',
    'Axolote Flexi': 'Flexi Axolotl',
    'Cobra Articulada': 'Articulated Snake',
    'Fidget Slider': 'Fidget Slider',
    'Cubo Infinito': 'Infinity Cube',
    'Tubarao Flexi': 'Flexi Shark',
    'Vaso Espiral': 'Spiral Vase',
    'Candeeiro Lua': 'Moon Lamp',
    'Quadro Litofania': 'Lithophane Frame',
    'Vaso Rosto': 'Face Planter',
    'Painel Geometrico de Parede': 'Geometric Wall Panel',
    'Presepio Minimalista': 'Minimalist Nativity',
    'Suporte de Auscultadores': 'Headphone Stand',
    'Organizador de Cabos': 'Cable Organizer',
    'Suporte de Telemovel': 'Phone Stand',
    'Caixa Modular Empilhavel': 'Stackable Storage Bin',
    'Abridor de Frascos': 'Jar Opener',
    'Suporte de Papel Higienico': 'Toilet Paper Holder',
    'Suporte de Chaves de Parede': 'Wall Key Holder',
    'Dock para Switch': 'Switch Dock',
    'Suporte de Comando': 'Controller Holder',
    'Suporte de Portatil': 'Laptop Stand',
    'Organizador de Secretaria': 'Desk Organizer',
    'Caixa para Auriculares': 'Earbud Case',
  },
  pt: {
    'Dragao Articulado': 'Dragão Articulado',
    'Tubarao Flexi': 'Tubarão Flexi',
    'Painel Geometrico de Parede': 'Painel Geométrico de Parede',
    'Presepio Minimalista': 'Presépio Minimalista',
    'Suporte de Telemovel': 'Suporte de Telemóvel',
    'Caixa Modular Empilhavel': 'Caixa Modular Empilhável',
    'Suporte de Papel Higienico': 'Suporte de Papel Higiénico',
    'Suporte de Portatil': 'Suporte de Portátil',
    'Organizador de Secretaria': 'Organizador de Secretária',
  },
  es: {
    'Polvo Articulado': 'Pulpo Articulado',
    'Dragao Articulado': 'Dragón Articulado',
    'Axolote Flexi': 'Ajolote Flexible',
    'Cobra Articulada': 'Serpiente Articulada',
    'Fidget Slider': 'Fidget Slider',
    'Cubo Infinito': 'Cubo Infinito',
    'Tubarao Flexi': 'Tiburón Flexible',
    'Vaso Espiral': 'Jarrón Espiral',
    'Candeeiro Lua': 'Lámpara de Luna',
    'Quadro Litofania': 'Cuadro Litofanía',
    'Vaso Rosto': 'Maceta con Rostro',
    'Painel Geometrico de Parede': 'Panel Geométrico de Pared',
    'Presepio Minimalista': 'Nacimiento Minimalista',
    'Suporte de Auscultadores': 'Soporte de Auriculares',
    'Organizador de Cabos': 'Organizador de Cables',
    'Suporte de Telemovel': 'Soporte de Teléfono',
    'Caixa Modular Empilhavel': 'Caja Apilable Modular',
    'Abridor de Frascos': 'Abridor de Frascos',
    'Suporte de Papel Higienico': 'Portarrollos',
    'Suporte de Chaves de Parede': 'Llavero de Pared',
    'Dock para Switch': 'Dock para Switch',
    'Suporte de Comando': 'Soporte de Mando',
    'Suporte de Portatil': 'Soporte de Portátil',
    'Organizador de Secretaria': 'Organizador de Escritorio',
    'Caixa para Auriculares': 'Estuche de Auriculares',
  },
};

export function nameLabel(locale: Locale, raw: string): string {
  return NAME_LABEL[locale][raw] ?? raw;
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
