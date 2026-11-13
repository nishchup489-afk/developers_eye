import type { Metadata, Viewport } from "next";
import { Geist, JetBrains_Mono } from "next/font/google";
import Ambient from "@/components/ambient";
import PrototypeBanner from "@/components/prototype-banner";
import { siteDescription, siteName, siteTagline, siteUrl, twitterHandle } from "@/lib/site";
import "./globals.css";

const sans = Geist({ subsets: ["latin"], variable: "--font-geist" });
const mono = JetBrains_Mono({ subsets: ["latin"], variable: "--font-jetbrains" });

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: {
    default: `${siteName} — ${siteTagline}`,
    template: `%s — ${siteName}`,
  },
  description: siteDescription,
  applicationName: siteName,
  keywords: [
    "developer search engine",
    "programming documentation search",
    "code search",
    "open source search engine",
    "Python docs",
    "JavaScript docs",
    "FastAPI",
    "Django",
    "React",
  ],
  authors: [{ name: "Nish", url: "https://github.com/nishchup489-afk" }],
  creator: "Nish",
  category: "technology",
  openGraph: {
    type: "website",
    siteName,
    title: `${siteName} — ${siteTagline}`,
    description: siteDescription,
    locale: "en_US",
  },
  twitter: {
    card: "summary_large_image",
    creator: twitterHandle,
    title: `${siteName} — ${siteTagline}`,
    description: siteDescription,
  },
  robots: {
    index: true,
    follow: true,
    googleBot: { index: true, follow: true, "max-image-preview": "large", "max-snippet": -1 },
  },
};
export const viewport: Viewport = {
  themeColor: "#0b0d09",
  colorScheme: "dark",
};
export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`${sans.variable} ${mono.variable}`}>
      <body>
        <PrototypeBanner />
        {children}
        <Ambient />
      </body>
    </html>
  );
}
