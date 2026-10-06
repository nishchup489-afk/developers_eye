import SearchExperience from "@/components/search-experience";
export const dynamic = "force-dynamic";
export default function Home() {
  return <SearchExperience mode={process.env.BACKEND_URL ? "live" : "demo"} />;
}
