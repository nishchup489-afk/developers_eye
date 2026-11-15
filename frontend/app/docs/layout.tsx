import Link from "next/link";
import { House } from "lucide-react";
import { DocsLayout } from "fumadocs-ui/layouts/docs";
import { RootProvider } from "fumadocs-ui/provider/next";
import { docsSource } from "@/lib/docs-source";
import "./docs.css";

export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <RootProvider theme={{ enabled: false }} search={{ options: { api: "/api/docs-search" } }}>
      <div className="dark docs-handbook min-h-screen bg-fd-background text-fd-foreground">
        <DocsLayout
          tree={docsSource.getPageTree()}
          // The brand returns to the search home page, like on the rest of the site.
          nav={{
            title: "Developer’s Eye",
            url: "/",
            // Shown in the mobile header, where the sidebar is hidden behind a toggle.
            children: (
              <Link href="/" className="docs-home-link" aria-label="Back to search">
                <House size={16} aria-hidden="true" />
                <span>Home</span>
              </Link>
            ),
          }}
          links={[
            {
              text: "Back to search",
              url: "/",
              icon: <House />,
              on: "menu",
            },
          ]}
          themeSwitch={{ enabled: false }}
        >
          {children}
        </DocsLayout>
      </div>
    </RootProvider>
  );
}
