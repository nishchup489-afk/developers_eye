"use client";

import { useCallback, useState } from "react";
import { BookOpen, Code2, MessageCircle } from "lucide-react";
import MoodyEye from "./moody-eye";

/** Developer’s Eye brand illustration: the WebGL eye plus its labels. */
export default function BrandEye() {
  const [webgl, setWebgl] = useState(true);
  const fallback = useCallback(() => setWebgl(false), []);

  return (
    <div className="eye-art reveal" aria-hidden="true">
      <div className="art-grid" />
      <div className="eye-stage">
        {webgl ? <MoodyEye onUnsupported={fallback} /> : <StaticEye />}
      </div>
      <div className="art-labels">
        <span className="art-label"><BookOpen size={12} /> docs</span>
        <span className="art-label"><Code2 size={12} /> code</span>
        <span className="art-label"><MessageCircle size={12} /> community</span>
      </div>
      <span className="art-coordinate">
        A LITTLE PERSPECTIVE CHANGES EVERYTHING.
      </span>
    </div>
  );
}

/** Line-art eye shown when WebGL is unavailable. */
function StaticEye() {
  return (
    <svg viewBox="0 95 500 210" className="eye-svg" fill="none">
      <defs>
        <radialGradient id="iris">
          <stop stopColor="#d6fc81" />
          <stop offset=".5" stopColor="#91aa60" />
          <stop offset="1" stopColor="#344625" />
        </radialGradient>
      </defs>
      <path d="M50 200Q250 20 450 200Q250 380 50 200Z" fill="#0c0f09" stroke="#91aa60" strokeWidth="2" />
      <g className="eye-core">
        <circle cx="250" cy="200" r="72" fill="url(#iris)" />
        {Array.from({ length: 56 }, (_, i) => (
          <line
            key={i}
            x1="250"
            y1="132"
            x2="250"
            y2="163"
            stroke="#17200e"
            opacity=".45"
            transform={`rotate(${i * (360 / 56)} 250 200)`}
          />
        ))}
        <circle cx="250" cy="200" r="34" fill="#11150e" />
        <circle
          cx="250"
          cy="200"
          r="25"
          stroke="#b4d578"
          strokeOpacity=".3"
        />
      </g>
      <path d="M20 200h25m410 0h25M250 97v10m0 186v10" stroke="#a1b67b" />
    </svg>
  );
}
