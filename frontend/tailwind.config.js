/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        // IO brand — green/white (placeholder scale, swap for exact logo hex)
        io: {
          50: "#e9f9f0",
          100: "#c9f0da",
          200: "#95e2b8",
          300: "#5fd093",
          400: "#34c77b",
          500: "#1ea562",
          600: "#157f52", // primary
          700: "#136443",
          800: "#124f38",
          900: "#0f3f2e",
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};
