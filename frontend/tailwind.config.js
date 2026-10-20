/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          950: "#070910",
          900: "#0b0f1a",
          850: "#0f1422",
          800: "#141b2d",
          700: "#1d2740",
          600: "#2a3756",
        },
        gold: {
          300: "#f5d98b",
          400: "#e9c46a",
          500: "#d4a43f",
        },
        ember: {
          400: "#ff8c5a",
          500: "#f26a3d",
        },
      },
      fontFamily: {
        display: ["Georgia", "Cambria", "serif"],
        sans: ["Inter", "system-ui", "Segoe UI", "sans-serif"],
      },
      boxShadow: {
        glow: "0 0 40px -10px rgba(233,196,106,0.35)",
      },
    },
  },
  plugins: [],
};
