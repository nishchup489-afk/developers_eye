// Display contract only; generation, evidence and validation belong to FastAPI.
export type OverviewSource = { id: number; title: string; url: string; snippet: string; kind?: string };
export type OverviewParagraph = { text: string; sources: number[] };
export type AIOverview = { paragraphs: OverviewParagraph[]; sources: OverviewSource[] };
