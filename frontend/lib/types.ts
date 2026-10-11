// Mirrors backend/common/models.py - change both together.
export type Source = "linkedin" | "instagram";
export type SourceStatus = "ok" | "thin" | "not_readable";
export const DIMENSIONS = [
  "interest_overlap",
  "values_alignment",
  "communication_chemistry",
  "lifestyle_fit",
  "growth_potential",
] as const;
export type Dimension = (typeof DIMENSIONS)[number];

export interface Claim { value: string; evidence: string; source: Source; confidence: number }
export interface Trait { value: string; evidence: string; confidence: number }
export interface Persona { summary: string; evidence: string[] }
export interface Profile {
  summary: string;
  needs: Claim[]; hobbies: Claim[]; interests: Claim[]; values: Claim[];
  communication_style: Trait; humor: Trait; energy: Trait;
  lifestyle: Claim[]; wants_in_partner: Claim[];
  linkedin_persona: Persona; instagram_persona: Persona;
  persona_gap: { score: number; description: string };
  identity_match: { score: number; reason: string };
  source_status: Record<Source, SourceStatus>;
}
export interface Rubric extends Record<Dimension, number> { would_meet_again: boolean; verdict: string }
export interface DateFlag { type: "unsupported_claim" | "spark" | "friction" | "repair"; note: string }
export interface DateTurn {
  idx: number; speaker: string; stage: string; public_text: string;
  private_note: string; chemistry: number; flags: DateFlag[];
}
export interface DateRecord {
  id: string; person_a: string; person_b: string; kind: "standard" | "scenario";
  status: "pending" | "running" | "done" | "failed"; turns: DateTurn[];
  score_a: Rubric | null; score_b: Rubric | null; // score_a = a's rating of b
  faithfulness_a: number | null; faithfulness_b: number | null; flagged_turns: number[];
}
export interface SSEEvent { event: "turn" | "chemistry" | "flag" | "done"; data: Record<string, unknown> }
export interface Briefing {
  introduce: { person_id: string; reason: string }[];
  warn: { person_id: string; reason: string }[];
  unsure: string[];
}
export interface PersonSummary { id: string; display_name: string; synthetic: boolean; profile: Profile | null }
export interface DemoBundle {
  people: PersonSummary[];
  dates: DateRecord[];
  matrix: (number | null)[][]; // matrix[i][j] = score person i gives person j (0-10)
  order: string[]; // person ids, row/col order of matrix
  stable_pairs: [string, string][];
  briefings: Record<string, Briefing>;
  best_moments: Record<string, string>; // "a|b" -> quoted line
}
