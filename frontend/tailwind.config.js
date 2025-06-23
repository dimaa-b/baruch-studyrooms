/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        'royal': ['Royal Gothic', 'sans-serif'],
        'sans': ['Royal Gothic', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'Oxygen', 'Ubuntu', 'Cantarell', 'Fira Sans', 'Droid Sans', 'Helvetica Neue', 'sans-serif'],
      },
      fontWeight: {
        'thin': 100,
        'light': 300,
        'normal': 400,
        'medium': 500,
        'bold': 700,
        'black': 900,
        'fat': 950,
      },
      colors: {
        primary: {
          DEFAULT: '#1B38E2',
          50: '#E8ECFE',
          100: '#D1DAFD',
          200: '#A3B5FB',
          300: '#7590F9',
          400: '#476BF7',
          500: '#1B38E2',
          600: '#1530C9',
          700: '#1028B0',
          800: '#0A2097',
          900: '#05187E'
        },
        secondary: '#ffffff',
      },
    },
  },
};
