const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export type SignalTier = "STRONG" | "LEAN" | "NONE" | "FADE";

export interface Market {
  id: string;
  platform: "kalshi" | "polymarket";
  question_text: string;
  category: "sports" | "politics" | "finance";
  resolution_criteria: string;
  close_time: string;
  resolved_at: string | null;
  outcome: "YES" | "NO" | null;
}

export interface Signal {
  id: string;
  market_id: string;
  model_probability: number;
  confidence_interval_low: number;
  confidence_interval_high: number;
  market_price: number;
  edge: number;
  signal_tier: SignalTier;
  sentiment_score: number;
  sentiment_weight: number;
  stats_weight: number;
  generated_at: string;
}

export interface EdgeReportItem {
  market_id: string;
  question_text: string;
  model_probability: number;
  market_price: number;
  edge: number;
  signal_tier: SignalTier;
}

async function get<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText}`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  listMarkets: () => get<Market[]>("/markets"),
  getMarket: (id: string) => get<Market>(`/markets/${id}`),
  getMarketSignals: (id: string) => get<Signal[]>(`/markets/${id}/signals`),
  getEdgeReport: () => get<EdgeReportItem[]>("/edge-report"),
};
