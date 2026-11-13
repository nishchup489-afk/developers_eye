"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const REPO_URL = "https://github.com/nishchup489-afk/developers_eye";

/** Site-wide notice that the public demo runs a small corpus. Hidden inside /admin. */
export default function PrototypeBanner() {
  const pathname = usePathname();
  if (pathname?.startsWith("/admin")) return null;

  const message = (
    <span className="prototype-banner__item">
      This is a small prototype with a ~100K-document dataset. For the full experience,{" "}
      <a href={REPO_URL} target="_blank" rel="noopener noreferrer">
        run it locally from GitHub
      </a>
      <span aria-hidden="true"> · </span>
      <Link href="/admin">Open the admin dashboard</Link>
    </span>
  );

  return (
    <aside className="prototype-banner" aria-label="Prototype notice">
      <div className="prototype-banner__track">
        {message}
        {/* Second copy makes the scroll loop seamless; inert keeps it out of reading and tab order. */}
        <span aria-hidden="true" inert className="prototype-banner__copy">
          {message}
        </span>
      </div>
    </aside>
  );
}
