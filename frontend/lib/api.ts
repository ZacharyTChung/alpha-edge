import { adminHeaders, backendAdminUrl } from "./admin-proxy";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export type SignalTier = "STRONG" | "LEAN" | "NONE" | "FADE";
export type Platform = "kalshi" | "polymarket";
export type Category = "sports" | "politics" | "finance";

export interface Market {
  id: string;
  platform: Platform;
  question_text: string;
  category: Category;
  resolution_criteria: string;
  liquidity: number;
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

export interface SentimentEvent {
  id: string;
  market_id: string;
  source: "twitter" | "reddit" | "news";
  source_url: string;
  entity: string;
  raw_text: string;
  sentiment: "positive" | "negative" | "neutral";
  credibility_weight: number;
  novelty_score: number;
  relevance_score: number;
  llm_reasoning: string | null;
  detected_at: string;
}

export interface EdgeReportItem {
  market_id: string;
  question_text: string;
  model_probability: number;
  market_price: number;
  edge: number;
  signal_tier: SignalTier;
  platform: Platform | null;
  category: Category | null;
  liquidity: number;
}

export interface DashboardStats {
  market_count: number;
  open_market_count: number;
  signal_count: number;
  sentiment_count: number;
  sentiment_last_24h: number;
  last_signal_at: string | null;
  by_tier: Record<SignalTier, number>;
}

export interface ClosingLineSample {
  market_id: string;
  question_text: string;
  initial_model_p: number;
  initial_market_p: number;
  final_market_p: number;
  initial_edge: number;
  market_moved_toward_edge: number;
  outcome: string | null;
}

export interface ClosingLineTracking {
  resolved_markets_with_signals: number;
  direction_hit_rate: number | null;
  avg_market_move_toward_edge: number | null;
  resolution_accuracy: number | null;
  samples: ClosingLineSample[];
}

export interface SourceContribution {
  source_key: string;
  n_events: number;
  beta_coefficient: number;
  avg_signed_score: number;
  raw_log_LR: number;
  capped_log_LR: number;
  was_capped: boolean;
  variance_contribution: number;
}

export interface DecisionInfo {
  decision: "BET_OVER" | "BET_UNDER" | "NO_BET";
  risk_level: "LOW" | "MEDIUM" | "HIGH";
  confidence: number;
  confidence_floor: number;
  deductions: string[];
  bonuses: string[];
  flags: Record<string, boolean>;
  reasoning: string;
  outcome_forecast: "YES" | "NO" | "UNCERTAIN";
  outcome_forecast_pct: number;
  saturated_market: boolean;
}

export interface PlayerPropInfo {
  is_player_prop: boolean;
  parsed: {
    player_name: string | null;
    prop_type: string | null;
    line: number | null;
    side: "over" | "under";
  };
  base_projection?: number;
  projected_mean?: number;
  adjusted_sd?: number;
  z_score?: number;
  model_prob_over?: number;
  model_prob_under?: number;
  n_games_used?: number;
  sd_source?: string;
  flags?: Record<string, boolean>;
  adjustments?: Array<{ name: string; value: number; note: string }>;
  error?: string;
}

export interface MarketCalculation {
  market: {
    question_text: string;
    platform: string;
    category: string;
    market_price_yes: number;
    decimal_odds_yes: number | null;
    implied_payout_per_dollar: number | null;
  };
  prior: { p_market: number; log_odds: number; comment: string };
  evidence: {
    n_events: number;
    delta_log_odds: number;
    per_source: SourceContribution[];
  };
  posterior: {
    log_odds: number;
    probability: number;
    variance_log_odds: number;
    sigma_log_odds: number;
    ci_95_low: number;
    ci_95_high: number;
  };
  edge: { edge: number; edge_pp: number; tier: string };
  betting: {
    decimal_odds_yes: number | null;
    b: number;
    full_kelly_fraction: number;
    half_kelly_fraction: number;
    capped_fraction: number;
    capped_pct_bankroll: number;
    was_capped_at_3pct: boolean;
    rule: string;
  };
  decision: DecisionInfo;
  player_prop: PlayerPropInfo | null;
  math_note: string;
}

async function get<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText}`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  listMarkets: (limit = 200) => get<Market[]>(`/markets?limit=${limit}`),
  getMarket: (id: string) => get<Market>(`/markets/${id}`),
  getMarketSignals: (id: string) => get<Signal[]>(`/markets/${id}/signals`),
  getEdgeReport: (minEdge = 0.03) =>
    get<EdgeReportItem[]>(`/edge-report?min_edge=${minEdge}&limit=200`),
  getMarketSentiment: (id: string) => get<SentimentEvent[]>(`/markets/${id}/sentiment`),
  getStats: () => get<DashboardStats>("/stats"),
  getClosingLine: async () => {
    const response = await fetch(backendAdminUrl("/admin/closing-line-tracking"), {
      cache: "no-store",
      headers: adminHeaders(),
    });
    if (!response.ok) {
      throw new Error(`${response.status} ${response.statusText}`);
    }
    return response.json() as Promise<ClosingLineTracking>;
  },
  refresh: (priority = false) =>
    fetch(`/api/admin/${priority ? "refresh-priority" : "refresh"}`, {
      method: "POST",
    }).then((r) => r.json()),
  reclassifyMarket: (id: string) =>
    fetch(`/api/admin/reclassify-market/${id}`, { method: "POST" }).then((r) => r.json()),
  getMarketCalculation: (id: string) => get<MarketCalculation>(`/markets/${id}/calculation`),
};
