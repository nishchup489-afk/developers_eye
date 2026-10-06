import { BookOpen, Code2, MessageCircle } from "lucide-react";

/** Developer’s Eye brand illustration. Motion is scoped by its parent. */
export default function BrandEye() {
  return (
    <div className="eye-art reveal" aria-hidden="true">
      <div className="art-grid" />
      <span className="art-coordinate coordinate-top">
        DE—01 / SIGNAL FOUND
      </span>
      <svg viewBox="0 0 500 400" className="eye-svg" fill="none">
        <defs>
          <radialGradient id="iris">
            <stop stopColor="#d6fc81" />
            <stop offset=".5" stopColor="#91aa60" />
            <stop offset="1" stopColor="#344625" />
          </radialGradient>
          <linearGradient id="eyeLine">
            <stop stopColor="#586044" stopOpacity=".1" />
            <stop offset=".5" stopColor="#d6fc81" />
            <stop offset="1" stopColor="#586044" stopOpacity=".1" />
          </linearGradient>
        </defs>
        <ellipse
          cx="250"
          cy="200"
          rx="213"
          ry="158"
          stroke="#414737"
          strokeDasharray="2 8"
        />
        <g className="orbit-spin">
          <circle cx="250" cy="200" r="184" stroke="#34392c" />
          <circle cx="250" cy="16" r="5" fill="#d6fc81" />
          <circle cx="250" cy="384" r="3" fill="#849664" />
        </g>
        {Array.from({ length: 12 }, (_, i) => (
          <ellipse
            key={i}
            cx="250"
            cy="200"
            rx={206 - i * 6}
            ry={122 - i * 7}
            stroke="url(#eyeLine)"
            strokeWidth=".8"
          />
        ))}
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
          <circle cx="266" cy="180" r="9" fill="#e8ffc3" />
          <circle cx="236" cy="215" r="3" fill="#b6d680" />
        </g>
        <path d="M20 200h25m410 0h25M250 0v20m0 360v20" stroke="#a1b67b" />
        <path
          d="M62 67V52h15m346 0h15v15M62 333v15h15m346 0h15v-15"
          stroke="#52613e"
        />
      </svg>
      <span className="art-label label-docs">
        <BookOpen size={12} /> docs
      </span>
      <span className="art-label label-code">
        <Code2 size={12} /> code
      </span>
      <span className="art-label label-community">
        <MessageCircle size={12} /> community
      </span>
      <span className="art-coordinate coordinate-bottom">
        A LITTLE PERSPECTIVE CHANGES EVERYTHING.
      </span>
    </div>
  );
}
