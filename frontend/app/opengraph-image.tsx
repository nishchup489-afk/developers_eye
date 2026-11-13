import { ImageResponse } from "next/og";

export const alt = "Developer’s Eye: less searching, more building";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function Image() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          padding: "80px",
          background: "#0b0d09",
          color: "#f2f4ec",
          fontFamily: "sans-serif",
        }}
      >
        <div style={{ display: "flex", fontSize: 88, fontWeight: 700, letterSpacing: -3 }}>
          developer’s<span style={{ color: "#d6fc81" }}>eye</span>.
        </div>
        <div style={{ display: "flex", marginTop: 24, fontSize: 40, color: "#b8bdae" }}>
          Less searching. More building.
        </div>
        <div style={{ display: "flex", marginTop: 48, fontSize: 28, color: "#8a9080" }}>
          Open-source search for developer docs, code and discussions
        </div>
      </div>
    ),
    size,
  );
}
