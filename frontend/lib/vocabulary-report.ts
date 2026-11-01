export type VocabularyTerm = { term: string; document_frequency: number; document_percent: number | null };
export type VocabularyMatch = VocabularyTerm & { similarity: number };
export type VocabularyBucket = { label: string; min: number; max: number | null; terms: number };
export type VocabularyReport = {
  version: 1; generated_at: string; query: string | null;
  summary: { total_terms: number; zero_frequency_terms: number; singleton_terms: number; overcounted_terms: number; max_document_frequency: number; total_postings: number; indexed_documents: number; average_terms_per_document: number | null; singleton_percent: number | null };
  distribution: VocabularyBucket[]; top_terms: VocabularyTerm[]; matches: VocabularyMatch[] | null;
};

const object = (v: unknown): v is Record<string, unknown> => !!v && typeof v === "object" && !Array.isArray(v);
const num = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v) && v >= 0;
const count = (v: unknown) => num(v) && Number.isSafeInteger(v);
const counts = (v: Record<string, unknown>, keys: string[]) => keys.every(k => count(v[k]));
const stamp = (v: unknown) => typeof v === "string" && Number.isFinite(Date.parse(v));
const percent = (v: unknown) => v === null || (num(v) && v <= 100);
const term = (t: unknown): t is Record<string, unknown> => object(t) && typeof t.term === "string" && count(t.document_frequency) && percent(t.document_percent);

// Validate at the server boundary so a partial snapshot never renders as an empty vocabulary.
export function isVocabularyReport(v: unknown): v is VocabularyReport {
  if (!object(v) || v.version !== 1 || !stamp(v.generated_at) || !(v.query === null || typeof v.query === "string") || !object(v.summary)) return false;
  const s = v.summary;
  if (!counts(s, ["total_terms", "zero_frequency_terms", "singleton_terms", "overcounted_terms", "max_document_frequency", "total_postings", "indexed_documents"]) || !(s.average_terms_per_document === null || num(s.average_terms_per_document)) || !percent(s.singleton_percent)) return false;
  if (!Array.isArray(v.distribution) || !v.distribution.every(b => object(b) && typeof b.label === "string" && count(b.min) && (b.max === null || count(b.max)) && count(b.terms))) return false;
  if (!Array.isArray(v.top_terms) || v.top_terms.length > 30 || !v.top_terms.every(term)) return false;
  return v.matches === null || (Array.isArray(v.matches) && v.matches.length <= 30 && v.matches.every(m => term(m) && num(m.similarity) && m.similarity <= 1));
}
