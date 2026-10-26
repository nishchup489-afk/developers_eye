"use client";

import { useState } from "react";
import { Check, Copy } from "lucide-react";

/** A titled code panel with a copy button. */
export default function CodeBlock({ title, code }: { title: string; code: string }) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1600);
    } catch {
      /* Clipboard access can be blocked; the code stays selectable. */
    }
  }

  return (
    <figure className="code-block">
      <figcaption>
        <span className="code-dots" aria-hidden="true">
          <i />
          <i />
          <i />
        </span>
        <span>{title}</span>
        <button
          type="button"
          className="code-copy"
          onClick={() => void copy()}
          aria-label={copied ? "Copied" : `Copy ${title}`}
        >
          {copied ? <Check size={14} /> : <Copy size={14} />}
          <span aria-live="polite">{copied ? "Copied" : "Copy"}</span>
        </button>
      </figcaption>
      <pre>
        <code>{code}</code>
      </pre>
    </figure>
  );
}
