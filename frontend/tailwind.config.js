/** @type {import('tailwindcss').Config} */
// Design tokens from the Sentinel AI brief — a premium cybersecurity SOC look.
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#050A12",
        sidebar: "#091321",
        card: "#0D1928",
        elevated: "#122238",
        border: "#1D3349",
        cyan: "#20D9F2",
        blue: "#338BFF",
        teal: "#13D6C1",
        success: "#20D99A",
        warning: "#FFBF47",
        critical: "#FF5268",
        text: "#ECF5FF",
        muted: "#8DA4BC",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "-apple-system", "Segoe UI", "Roboto", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
      boxShadow: {
        glow: "0 0 20px rgba(32, 217, 242, 0.15)",
        "glow-blue": "0 0 24px rgba(51, 139, 255, 0.18)",
        card: "0 1px 2px rgba(0,0,0,0.4), 0 0 0 1px rgba(29,51,73,0.6)",
      },
      keyframes: {
        pulseGlow: {
          "0%, 100%": { opacity: "0.6" },
          "50%": { opacity: "1" },
        },
        fadeIn: {
          from: { opacity: "0", transform: "translateY(4px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
      },
      animation: {
        pulseGlow: "pulseGlow 2.4s ease-in-out infinite",
        fadeIn: "fadeIn 0.3s ease-out",
      },
    },
  },
  plugins: [],
};
