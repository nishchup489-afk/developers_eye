import SearchExperience from "@/components/search-experience";
import { redirect } from "next/navigation";
import { isSearchMode } from "@/lib/search";
export const dynamic = "force-dynamic";
export default async function Home({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const params = await searchParams;
  // Keep previously shared home-page search URLs working.
  if (typeof params.q === "string" && params.q.trim()) {
    const query = new URLSearchParams({ q: params.q.trim() });
    if (typeof params.source === "string") query.set("source", params.source);
    if (isSearchMode(params.mode) && params.mode !== "all")
      query.set("mode", params.mode);
    redirect(`/search?${query}`);
  }
  return <SearchExperience mode={process.env.BACKEND_URL ? "live" : "demo"} />;
}
