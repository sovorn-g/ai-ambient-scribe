import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        vellum:   "#F4F2EB",   // document paper background
        nuit:     "#16162A",   // archival deep blue-black
        dusty:    "#7A6E60",   // warm secondary text
        alert:    "#B91C1C",   // DRAFT alert red
        clinical: "#1B4D82",   // institutional blue (clinician role, CTAs)
        ruled:    "#E6E1D5",   // warm divider / border
      },
      fontFamily: {
        grotesk: ["var(--font-grotesk)", "system-ui", "sans-serif"],
        lora:    ["var(--font-lora)", "Georgia", "serif"],
      },
    },
  },
  plugins: [],
};

export default config;
