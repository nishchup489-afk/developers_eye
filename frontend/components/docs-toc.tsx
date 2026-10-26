"use client";

import { useEffect, useState } from "react";

/** Sticky contents list that highlights the section in view. */
export default function DocsToc({
  sections,
}: {
  sections: readonly { id: string; title: string }[];
}) {
  const [active, setActive] = useState(sections[0]?.id);

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((entry) => entry.isIntersecting)
          .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
        if (visible[0]) setActive(visible[0].target.id);
      },
      { rootMargin: "-15% 0px -65% 0px" },
    );
    sections.forEach(({ id }) => {
      const el = document.getElementById(id);
      if (el) observer.observe(el);
    });
    return () => observer.disconnect();
  }, [sections]);

  return (
    <nav className="docs-toc" aria-label="On this page">
      <span className="eyebrow">ON THIS PAGE</span>
      <ol>
        {sections.map(({ id, title }, index) => (
          <li key={id}>
            <a
              href={`#${id}`}
              className={active === id ? "active" : undefined}
              aria-current={active === id ? "location" : undefined}
            >
              <span>0{index + 1}</span>
              {title}
            </a>
          </li>
        ))}
      </ol>
    </nav>
  );
}
