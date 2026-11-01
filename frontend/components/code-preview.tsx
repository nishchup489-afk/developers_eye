"use client";

import { useMemo, useState } from "react";
import { Check, CodeXml, Copy, WrapText, X } from "lucide-react";
import { detectLanguage, highlight, toLines } from "@/lib/highlight";

/** Code pasted into the search bar, shown as a highlighted code card. */
export default function CodePreview({
  code,
  note,
  onRemove,
}: {
  code: string;
  note?: string;
  onRemove: () => void;
}) {
  const [wrap, setWrap] = useState(false);
  const [copied, setCopied] = useState(false);
  const language = useMemo(() => detectLanguage(code), [code]);
  const lines = useMemo(() => toLines(highlight(code, language)), [code, language]);

  async function copy() {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      /* Clipboard access can be blocked; the code is still selectable. */
    }
  }

  return (
    <figure className={`search-code-preview${wrap ? " is-wrapped" : ""}`}>
      <figcaption>
        <span className="search-code-language">
          <CodeXml size={15} />
          {language.name}
        </span>
        <span className="search-code-actions">
          <button
            type="button"
            aria-label={wrap ? "Turn off line wrap" : "Wrap long lines"}
            aria-pressed={wrap}
            title="Wrap lines"
            className={wrap ? "active" : ""}
            onClick={() => setWrap(!wrap)}
          >
            <WrapText size={15} />
          </button>
          <button
            type="button"
            aria-label={copied ? "Copied" : "Copy code"}
            title="Copy"
            onClick={() => void copy()}
          >
            {copied ? <Check size={15} /> : <Copy size={15} />}
          </button>
          <button
            type="button"
            aria-label="Remove pasted code"
            title="Remove"
            onClick={onRemove}
          >
            <X size={15} />
          </button>
        </span>
      </figcaption>
      <pre>
        <code>
          {lines.map((line, i) => (
            <span className="code-line" key={i}>
              {line.length
                ? line.map((token, j) =>
                    token.type === "plain" ? (
                      token.text
                    ) : (
                      <span className={`tok-${token.type}`} key={j}>
                        {token.text}
                      </span>
                    ),
                  )
                : " "}
            </span>
          ))}
        </code>
      </pre>
      {note && <p className="search-code-note">{note}</p>}
    </figure>
  );
}
