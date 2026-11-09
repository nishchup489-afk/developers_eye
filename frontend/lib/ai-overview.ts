export type OverviewSource = { id: number; title: string; url: string; snippet: string; kind?: string };
export type OverviewParagraph = { text: string; sources: number[] };
export type AIOverview = { paragraphs: OverviewParagraph[]; sources: OverviewSource[] };

/** Model text stays plain text. URLs come only from the signed search context. */
export function parseOverview(value: unknown, sources: OverviewSource[]): AIOverview | null {
  if (!value || typeof value !== "object") return null;
  const paragraphs = (value as Record<string, unknown>).paragraphs;
  if (!Array.isArray(paragraphs) || paragraphs.length > 3) return null;
  const validIds = new Set(sources.map((source) => source.id));
  const parsed: OverviewParagraph[] = [];
  for (const item of paragraphs) {
    if (!item || typeof item !== "object") return null;
    const { text, sources: ids } = item as Record<string, unknown>;
    if (typeof text !== "string" || !text.trim() || text.length > 700 ||
      !Array.isArray(ids) || ids.length < 1 || ids.length > sources.length ||
      !ids.every((id) => Number.isInteger(id) && validIds.has(id))) return null;
    parsed.push({ text: text.trim(), sources: [...new Set(ids as number[])] });
  }
  const cited = new Set(parsed.flatMap((paragraph) => paragraph.sources));
  return { paragraphs: parsed, sources: sources.filter((source) => cited.has(source.id)) };
}
