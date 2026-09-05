export type ComponentKey = 'gap' | 'trend' | 'margin';
export type Parts = Partial<Record<ComponentKey, number>>;

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
}

export interface ModelsResponse {
  models: ModelSummary[];
  categories: string[];
}

export interface HistoryPoint {
  day: string;
  demand_raw: number | null;
  competition_raw: number | null;
  margin_est: number | null;
}

export interface ModelDetail extends ModelSummary {
  history: HistoryPoint[];
}
