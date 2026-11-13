// Public origin used for canonical URLs, Open Graph, robots.txt and sitemap.xml.
// SITE_URL wins; on Vercel the production domain is provided automatically.
function resolveSiteUrl(): string {
  const explicit = process.env.SITE_URL?.trim();
  if (explicit) return explicit.replace(/\/+$/, "");
  const vercel = process.env.VERCEL_PROJECT_PRODUCTION_URL?.trim();
  if (vercel) return `https://${vercel}`;
  return "http://localhost:3000";
}

export const siteUrl = resolveSiteUrl();
export const siteName = "Developer’s Eye";
export const siteTagline = "Less searching. More building.";
export const siteDescription =
  "Developer’s Eye is an open-source search engine for programming docs, code and developer discussions. Search Python, JavaScript, FastAPI, Django, React and more in one focused place.";
export const twitterHandle = "@Nishchup489";
export const repoUrl = "https://github.com/nishchup489-afk/developers_eye";
