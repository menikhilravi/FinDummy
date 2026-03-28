import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // Neon accents
        neon: {
          green: "#00ff88",
          red: "#ff3355",
          blue: "#00d4ff",
          yellow: "#ffcc00",
        },
        // Dark background palette
        bg: {
          base: "#080c10",
          surface: "#0d1117",
          card: "#111827",
          border: "#1f2937",
          hover: "#1a2332",
        },
        // Text
        text: {
          primary: "#e2e8f0",
          secondary: "#94a3b8",
          muted: "#475569",
        },
      },
      fontFamily: {
        mono: ["JetBrains Mono", "Fira Code", "Consolas", "monospace"],
        sans: ["Inter", "system-ui", "sans-serif"],
      },
      animation: {
        "pulse-neon": "pulse-neon 2s ease-in-out infinite",
        "slide-up": "slide-up 0.3s ease-out",
        "fade-in": "fade-in 0.2s ease-out",
        "glow-green": "glow-green 1.5s ease-in-out infinite alternate",
        "glow-red": "glow-red 1.5s ease-in-out infinite alternate",
        "typing": "typing 0.05s steps(1) infinite",
      },
      keyframes: {
        "pulse-neon": {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.5" },
        },
        "slide-up": {
          "0%": { transform: "translateY(10px)", opacity: "0" },
          "100%": { transform: "translateY(0)", opacity: "1" },
        },
        "fade-in": {
          "0%": { opacity: "0" },
          "100%": { opacity: "1" },
        },
        "glow-green": {
          from: { boxShadow: "0 0 5px #00ff88, 0 0 10px #00ff88" },
          to: { boxShadow: "0 0 20px #00ff88, 0 0 40px #00ff88" },
        },
        "glow-red": {
          from: { boxShadow: "0 0 5px #ff3355, 0 0 10px #ff3355" },
          to: { boxShadow: "0 0 20px #ff3355, 0 0 40px #ff3355" },
        },
        "typing": {
          "0%, 100%": { borderColor: "transparent" },
          "50%": { borderColor: "#00ff88" },
        },
      },
      backdropBlur: {
        xs: "2px",
      },
      boxShadow: {
        "neon-green": "0 0 20px rgba(0, 255, 136, 0.3)",
        "neon-red": "0 0 20px rgba(255, 51, 85, 0.3)",
        "glass": "0 8px 32px rgba(0, 0, 0, 0.4)",
      },
    },
  },
  plugins: [],
};

export default config;
