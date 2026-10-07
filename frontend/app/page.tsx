import SearchExperience from "@/components/search-experience";
import { redirect } from "next/navigation";
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
    redirect(`/search?${query}`);
  }
  return <SearchExperience mode={process.env.BACKEND_URL ? "live" : "demo"} />;
}
