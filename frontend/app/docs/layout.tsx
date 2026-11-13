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
          nav={{ title: "Developer’s Eye", url: "/docs" }}
          links={[{ text: "Back to search", url: "/" }]}
          themeSwitch={{ enabled: false }}
        >
          {children}
        </DocsLayout>
      </div>
    </RootProvider>
  );
}
