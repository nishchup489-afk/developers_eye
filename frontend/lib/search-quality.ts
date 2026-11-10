// Shapes match backend.admin_services.search_quality (ADR-0057).
export const STAGES = ["retrieval", "ranking", "metadata", "snippets"] as const;
export type Stage = (typeof STAGES)[number];
export type SlowSearch = {
  recorded_at: string; query: string; mode: string; category: string | null; page: number; outcome: string;
  elapsed_ms: number; result_count: number | null; stages: Partial<Record<Stage, number>>; stopped_in: string | null;
};
export type RepeatedSlowSearch = { query: string; mode: string; count: number; timed_out: number; max_ms: number; mean_ms: number };
export type SlowSearchReport = {
  hours: number; threshold_ms: number; total: number; timed_out: number; stage_means_ms: Partial<Record<Stage, number>>;
  timeouts_by_stage: Record<string, number>; repeated: RepeatedSlowSearch[]; queries: SlowSearch[];
};
export type RankerMetrics = Record<string, number | null>;
export type EvaluationRow = {
  id: string; query: string; mode: string; stratum: string; source: string | null; note: string; no_relevant_documents: boolean;
  pooled: number; graded: number; positives: number; last_pooled_at: string | null; candidate_count: number | null;
  status: string; reason?: string; candidate_recall_at_100_per_channel?: number | null; bm25?: RankerMetrics; postgresql?: RankerMetrics;
};
export type EvaluationReport = {
  k: 5 | 10; human_set_available: boolean; queries: EvaluationRow[];
  aggregate: { complete_queries: number; total_queries: number; status: string; bm25: RankerMetrics; postgresql: RankerMetrics; candidate_recall: number | null };
};
export type Judgment = { url: string; title: string; grade: number | null; note: string; origin: "pool" | "added"; judged_by: string | null; judged_at: string | null };
export type JudgingQuery = { id: string; query: string; mode: string; stratum: string; source: string | null; note: string; no_relevant_documents: boolean; judgments: Judgment[] };

export const MODES = ["all", "text", "code"] as const;
export const MAX_NOTE_CHARS = 2000;
export const QUERY_ID = /^[A-Za-z0-9_-]{1,32}$/;

type Obj = Record<string, unknown>;
const object = (v: unknown): v is Obj => !!v && typeof v === "object" && !Array.isArray(v);
const num = (v: unknown) => typeof v === "number" && Number.isFinite(v);
const nullableNum = (v: unknown) => v === null || num(v);
const str = (v: unknown) => typeof v === "string";
const nullableStr = (v: unknown) => v === null || str(v);
const numberMap = (v: unknown) => object(v) && Object.values(v).every(num);
const metrics = (v: unknown) => object(v) && Object.values(v).every(nullableNum);

function isSlowSearch(v: unknown): v is SlowSearch {
  return object(v) && str(v.recorded_at) && str(v.query) && str(v.mode) && nullableStr(v.category) && num(v.page) && str(v.outcome)
    && num(v.elapsed_ms) && nullableNum(v.result_count) && numberMap(v.stages) && nullableStr(v.stopped_in);
}

export function isSlowSearchReport(v: unknown): v is SlowSearchReport {
  return object(v) && num(v.hours) && num(v.threshold_ms) && num(v.total) && num(v.timed_out) && numberMap(v.stage_means_ms)
    && numberMap(v.timeouts_by_stage) && Array.isArray(v.queries) && v.queries.every(isSlowSearch)
    && Array.isArray(v.repeated) && v.repeated.every(r => object(r) && str(r.query) && str(r.mode) && num(r.count) && num(r.timed_out) && num(r.max_ms) && num(r.mean_ms));
}

function isEvaluationRow(v: unknown): v is EvaluationRow {
  return object(v) && str(v.id) && str(v.query) && str(v.mode) && str(v.stratum) && nullableStr(v.source) && str(v.note)
    && typeof v.no_relevant_documents === "boolean" && num(v.pooled) && num(v.graded) && num(v.positives)
    && nullableStr(v.last_pooled_at) && nullableNum(v.candidate_count) && str(v.status)
    && (v.bm25 === undefined || metrics(v.bm25)) && (v.postgresql === undefined || metrics(v.postgresql));
}

export function isEvaluationReport(v: unknown): v is EvaluationReport {
  if (!object(v) || (v.k !== 5 && v.k !== 10) || typeof v.human_set_available !== "boolean" || !Array.isArray(v.queries) || !v.queries.every(isEvaluationRow)) return false;
  const a = v.aggregate;
  return object(a) && num(a.complete_queries) && num(a.total_queries) && str(a.status) && metrics(a.bm25) && metrics(a.postgresql) && nullableNum(a.candidate_recall);
}

export function isJudgingQuery(v: unknown): v is JudgingQuery {
  return object(v) && str(v.id) && str(v.query) && str(v.mode) && str(v.stratum) && nullableStr(v.source) && str(v.note)
    && typeof v.no_relevant_documents === "boolean" && Array.isArray(v.judgments)
    && v.judgments.every(j => object(j) && str(j.url) && str(j.title) && (j.grade === null || [0, 1, 2, 3].includes(j.grade as number))
      && str(j.note) && (j.origin === "pool" || j.origin === "added") && nullableStr(j.judged_by) && nullableStr(j.judged_at));
}

// Search text can be personal, so only administrators see it; viewers keep the timings.
export function redactSlowSearchReport(report: SlowSearchReport, role: "admin" | "viewer" | "guest"): SlowSearchReport {
  if (role === "admin") return report;
  return { ...report, repeated: report.repeated.map((r, i) => ({ ...r, query: `Query ${i + 1}` })), queries: report.queries.map(q => ({ ...q, query: "(hidden)" })) };
}

const httpUrl = (v: unknown) => {
  if (!str(v) || (v as string).length > 2048) return false;
  try { return ["http:", "https:"].includes(new URL(v as string).protocol); } catch { return false; }
};
const note = (v: unknown) => v === undefined || v === null || (str(v) && (v as string).length <= MAX_NOTE_CHARS);

// Write bodies are checked here too, so only well-formed fields ever reach the backend.
export function judgmentBody(v: unknown): { url: string; grade: number | null; note: string; add: boolean } | null {
  if (!object(v) || !httpUrl(v.url) || !(v.grade === null || [0, 1, 2, 3].includes(v.grade as number)) || !note(v.note) || !(v.add === undefined || typeof v.add === "boolean")) return null;
  return { url: v.url as string, grade: v.grade as number | null, note: (v.note as string | undefined) ?? "", add: v.add === true };
}

export function queryBody(v: unknown): { query: string; mode: string; source: string | null; stratum: string; note: string; no_relevant_documents: boolean } | null {
  if (!object(v) || !str(v.query) || !(v.query as string).trim() || (v.query as string).length > 256 || !MODES.includes(v.mode as (typeof MODES)[number])) return null;
  if (!(v.source === undefined || v.source === null || (str(v.source) && (v.source as string).length <= 64)) || !(v.stratum === undefined || (str(v.stratum) && (v.stratum as string).length <= 64))) return null;
  if (!note(v.note) || !(v.no_relevant_documents === undefined || typeof v.no_relevant_documents === "boolean")) return null;
  return { query: (v.query as string).trim(), mode: v.mode as string, source: (v.source as string | null | undefined) || null, stratum: (v.stratum as string | undefined) ?? "", note: (v.note as string | undefined) ?? "", no_relevant_documents: v.no_relevant_documents === true };
}
