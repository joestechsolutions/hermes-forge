/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        hermes: {
          bg: '#0a0a0a',
          card: '#141414',
          border: '#262626',
          primary: '#00dc82',
          accent: '#3b82f6',
        }
      }
    },
  },
  plugins: [],
}