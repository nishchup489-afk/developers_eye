import SearchExperience, { type SearchFilter } from "@/components/search-experience";
import { isSearchMode, sourceNames } from "@/lib/search";

export const dynamic = "force-dynamic";
export const metadata = {
  title: "Search",
  // Result pages are thin, query-specific copies of other sites' content.
  robots: { index: false, follow: true },
};

export default async function SearchPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const params = await searchParams;
  const query = typeof params.q === "string" ? params.q.trim() : "";
  const source = typeof params.source === "string" ? params.source : "all";
  const filter: SearchFilter =
    source === "discussions" || Object.hasOwn(sourceNames, source)
      ? (source as SearchFilter)
      : "all";
  const rawMode = params.mode;
  const searchMode = isSearchMode(rawMode) ? rawMode : "all";
  const saved = params.saved === "1";
  const requestedSize = Number(params.limit ?? 20);
  const pageSize = Number.isInteger(requestedSize) && requestedSize >= 1 && requestedSize <= 50 ? requestedSize : 20;
  const requestedPage = Number(params.page ?? 1);
  const page = Number.isInteger(requestedPage) && requestedPage >= 1 && (requestedPage - 1) * pageSize <= 1000 ? requestedPage : 1;
  const language = typeof params.language === "string" && /^[a-zA-Z]{2,3}(?:-[a-zA-Z0-9]{2,8}){0,2}$/.test(params.language) ? params.language : "";

  return (
    <SearchExperience
      key={JSON.stringify([query, filter, searchMode, saved, page, pageSize, language])}
      mode={process.env.BACKEND_URL ? "live" : "demo"}
      resultsPage
      initialQuery={query}
      initialFilter={filter}
      initialSearchMode={searchMode}
      initialPage={page}
      initialPageSize={pageSize}
      initialLanguage={language}
      savedPage={saved}
    />
  );
}
