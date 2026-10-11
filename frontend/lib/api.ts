import type { Briefing, DateRecord, DemoBundle, PersonSummary, Profile, Rubric } from "./types";

export const API_URL = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, { ...init, headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) } });
  } catch {
    throw new ApiError(0, `Cannot reach the backend at ${API_URL}. Is it running?`);
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const j = await res.json();
      detail = typeof j?.detail === "string" ? j.detail : JSON.stringify(j?.detail ?? j);
    } catch {
      /* ignore */
    }
    throw new ApiError(res.status, detail || `HTTP ${res.status}`);
  }
  return (await res.json()) as T;
}

/** GET /api/people/{id}. Status strings beyond these are tolerated. */
export interface PersonRecord {
  id: string;
  display_name?: string | null;
  status: string;
  synthetic?: boolean;
  profile: Profile | null;
  error?: string | null;
}
export const TERMINAL_STATUSES = ["ready", "done", "complete", "completed", "analyzed", "failed", "error", "deleted"];
export const FAILED_STATUSES = ["failed", "error"];

/**
 * GET /api/people/{id}/rankings. The spec only says "ranked matches with per-dimension scores",
 * so the client accepts either a bare array or { matches: [...] }.
 * mine = this person's rating of the match; theirs = the match's rating of this person.
 */
export interface RankingMatch {
  person_id: string;
  display_name?: string;
  synthetic?: boolean;
  date_id?: string;
  mine: Rubric | null;
  theirs: Rubric | null;
  best_moment?: string;
}
export type RankingsResponse = RankingMatch[] | { person?: PersonSummary; matches: RankingMatch[] };

/** GET /api/pool/matrix: same matrix fields as the demo bundle (people optional). */
export interface PoolMatrix {
  order: string[];
  matrix: (number | null)[][];
  stable_pairs: [string, string][];
  people?: PersonSummary[];
}

export type { Briefing, DateRecord, DemoBundle };

// ---- demo bundle (static JSON, no backend) ----
let demoPromise: Promise<DemoBundle> | null = null;
export function loadDemo(): Promise<DemoBundle> {
  if (!demoPromise) {
    demoPromise = fetch("/demo/demo.json")
      .then((r) => {
        if (!r.ok) throw new ApiError(r.status, "Demo data not found.");
        return r.json() as Promise<DemoBundle>;
      })
      .catch((e) => {
        demoPromise = null;
        throw e;
      });
  }
  return demoPromise;
}
