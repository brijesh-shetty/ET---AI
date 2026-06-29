/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        canvas: "#020617",
        panel: "#0f172a",
        "panel-2": "#1e293b",
        "border-soft": "#334155",
        accent: "#6366f1",
        "accent-soft": "#4f46e5",
        warn: "#f59e0b",
        critical: "#f43f5e",
        good: "#10b981",
      },
      fontFamily: {
        sans: [
          "Inter",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "Roboto",
          "sans-serif",
        ],
        mono: [
          "JetBrains Mono",
          "ui-monospace",
          "SFMono-Regular",
          "Menlo",
          "Consolas",
          "monospace",
        ],
      },
      boxShadow: {
        panel: "0 1px 0 0 rgba(148,163,184,0.06) inset, 0 0 0 1px rgba(51,65,85,0.6)",
      },
    },
  },
  plugins: [],
};
