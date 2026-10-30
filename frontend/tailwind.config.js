/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      // Colors of the PoliGPT logo, based on the Poli/UFRJ logos: navy 700 is the "Poli" and gold 500 the gear
      colors: {
        navy: {
          50: '#EEF2FA',
          100: '#DCE3F4',
          200: '#BAC7EA',
          300: '#9DB0E2',
          400: '#6B86CF',
          500: '#4766B8',
          600: '#2C4793',
          700: '#1A2D6D',
          800: '#132256',
          900: '#0D173B',
        },
        gold: {
          500: '#FCB400',
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