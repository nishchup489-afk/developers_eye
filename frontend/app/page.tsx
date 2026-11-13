import type { Metadata } from "next";
import SearchExperience from "@/components/search-experience";
import { redirect } from "next/navigation";
import { isSearchMode } from "@/lib/search";
import { repoUrl, siteDescription, siteName, siteUrl } from "@/lib/site";
export const dynamic = "force-dynamic";
export const metadata: Metadata = {
  alternates: { canonical: "/" },
};
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
  const structuredData = {
    "@context": "https://schema.org",
    "@type": "WebSite",
    name: siteName,
    url: `${siteUrl}/`,
    description: siteDescription,
    sameAs: [repoUrl],
    potentialAction: {
      "@type": "SearchAction",
      target: { "@type": "EntryPoint", urlTemplate: `${siteUrl}/search?q={search_term_string}` },
      "query-input": "required name=search_term_string",
    },
  };
  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(structuredData).replace(/</g, "\\u003c") }}
      />
      <SearchExperience mode={process.env.BACKEND_URL ? "live" : "demo"} />
    </>
  );
}
