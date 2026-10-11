import type { Config } from "tailwindcss";
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: { extend: { colors: { accent: { DEFAULT: "#be185d", soft: "#fce7f3" } } } },
  plugins: [],
};
export default config;
