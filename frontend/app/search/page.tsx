import SearchExperience, { type SearchFilter } from "@/components/search-experience";
import { sourceNames } from "@/lib/search";

export const dynamic = "force-dynamic";
export const metadata = { title: "Search — Developer’s Eye" };

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
  const saved = params.saved === "1";

  return (
    <SearchExperience
      key={JSON.stringify([query, filter, saved])}
      mode={process.env.BACKEND_URL ? "live" : "demo"}
      resultsPage
      initialQuery={query}
      initialFilter={filter}
      savedPage={saved}
    />
  );
}
