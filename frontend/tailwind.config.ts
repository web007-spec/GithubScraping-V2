import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["var(--font-inter)", "system-ui", "sans-serif"],
        roboto: ["var(--font-roboto)", "Roboto", "Helvetica", "Arial", "sans-serif"],
      },
      colors: {
        github: { DEFAULT: "#e5edf7", light: "#9aa8bb", muted: "#64748b" },
        accent: { DEFAULT: "#38bdf8", hover: "#0ea5e9", soft: "#0f2d3e" },
        surface: {
          DEFAULT: "#111827",
          subtle: "#0b1220",
          border: "#253244",
        },
      },
      boxShadow: {
        card: "0 16px 40px -28px rgb(0 0 0 / 0.9)",
        elevated: "0 24px 70px -38px rgb(0 0 0 / 0.95)",
      },
      borderRadius: {
        xl: "1rem",
        "2xl": "1.25rem",
      },
    },
  },
  plugins: [],
};
export default config;
