import { ImageResponse } from "next/og";

export const alt = "Orvani — Boas escolhas em um só lugar.";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function OpenGraphImage() {
  return new ImageResponse(
    <div
      style={{
        width: "100%",
        height: "100%",
        display: "flex",
        position: "relative",
        alignItems: "center",
        justifyContent: "center",
        overflow: "hidden",
        background: "#0B1020",
        color: "#F7F8FC",
      }}
    >
      <div style={{ position: "absolute", width: 540, height: 540, borderRadius: 270, background: "#635BFF", top: -260, right: -110, opacity: 0.9 }} />
      <div style={{ position: "absolute", width: 240, height: 240, borderRadius: 120, background: "#FF6B4A", bottom: -120, left: 80 }} />
      <div style={{ display: "flex", width: 980, alignItems: "center", gap: 54 }}>
        <div style={{ display: "flex", width: 160, height: 160, border: "24px solid #F7F8FC", borderRightColor: "#635BFF", borderRadius: 80, position: "relative" }}>
          <div style={{ position: "absolute", width: 34, height: 34, borderRadius: 17, background: "#FF6B4A", right: -12, top: 20 }} />
        </div>
        <div style={{ display: "flex", flexDirection: "column" }}>
          <div style={{ fontSize: 104, fontWeight: 800, letterSpacing: -5 }}>Orvani</div>
          <div style={{ marginTop: 12, fontSize: 36, color: "#D8DAE7" }}>Boas escolhas em um só lugar.</div>
        </div>
      </div>
    </div>,
    size,
  );
}
