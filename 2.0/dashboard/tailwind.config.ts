import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#0c1324",
        paper: "#f5f1e8",
        brass: "#b9853b",
        fern: "#3d7057",
        oxblood: "#6f2e2e",
        slateblue: "#31415f",
      },
      boxShadow: {
        panel: "0 24px 80px rgba(12, 19, 36, 0.14)",
      },
    },
  },
  plugins: [],
};

export default config;
