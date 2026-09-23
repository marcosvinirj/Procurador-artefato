export type ComponentKey = 'gap' | 'trend' | 'margin';
export type Parts = Partial<Record<ComponentKey, number>>;

export type Plan = 'free' | 'pro' | 'premium';

/** Um anuncio da Etsy para o termo. O que chega depende do plano: o gratis so
 *  recebe `image` do lider; Pro o lider inteiro; Premium os primeiros 4. */
export interface Listing {
  title?: string | null;
  url?: string | null;
  price?: number | null;
  currency?: string | null;
  image?: string | null;
}

export interface ModelSummary {
  id: string;
  name: string;
  category: string;
  keyword: string;
  synonyms: string[];
  score: number;
  demand_norm: number | null;
  competition_norm: number | null;
  components: Parts;
  contributions: Parts;
  updated_at: string | null;
  showcase: Listing[];
  /** A pesquisa exata que gerou os numeros (Pro e Premium). */
  search_url: string | null;
}

export interface ModelsResponse {
  models: ModelSummary[];
  categories: string[];
  /** Plano gratis: um item por modelo bloqueado, na ordem do ranking — so a
   *  categoria e a faixa larga do score, nunca o nome nem os numeros. */
  locked: { category: string; band: [number, number] }[];
  plan: Plan;
}

export interface HistoryPoint {
  day: string;
  demand_raw: number | null;
  competition_raw: number | null;
  margin_est: number | null;
}

export interface ModelDetail extends ModelSummary {
  plan: Plan;
  history: HistoryPoint[];
}
