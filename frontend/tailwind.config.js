/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        blue: {
          100: '#E6F0FF',
          200: '#CCE0FF',
          300: '#99C0FF',
          400: '#66A0FF',
          500: '#3380FF',
          600: '#0055CC',
          700: '#004099',
          800: '#002B66',
          900: '#001533',
        },
      },
      animation: {
        fadeIn: 'fadeIn 0.3s ease-in-out',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: 0, transform: 'translateY(10px)' },
          '100%': { opacity: 1, transform: 'translateY(0)' },
        },
      },
    },
  },
  plugins: [
    require('tailwind-scrollbar')({ nocompatible: true }),
    // Styles the markdown of the answers (classes prose, prose-invert...)
    require('@tailwindcss/typography'),
  ],
};