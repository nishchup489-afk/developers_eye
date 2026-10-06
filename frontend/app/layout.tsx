import type { Metadata } from "next";
import "./globals.css";
export const metadata: Metadata = {
  title: "Developer’s Eye — Less searching. More building.",
  description: "The docs, the code, the conversation. Explore developer knowledge in one focused search experience.",
};
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return <html lang="en"><body>{children}</body></html>;
}
