/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // System architectural palette based on HomeOps design spec
        canvas: {
          light: '#F3F1EB',
          dark: '#101210',
          DEFAULT: '#F3F1EB',
        },
        surface: {
          light: '#FAF9F6',
          dark: '#181B18',
          DEFAULT: '#FAF9F6',
        },
        'surface-elevated': {
          light: '#FFFFFF',
          dark: '#222622',
        },
        'text-main': {
          light: '#171918',
          dark: '#EFF1EC',
          DEFAULT: '#171918',
        },
        'text-muted': {
          light: '#676B68',
          dark: '#969D96',
          DEFAULT: '#676B68',
        },
        'border-main': {
          light: '#D9D8D2',
          dark: '#2D322E',
          DEFAULT: '#D9D8D2',
        },
        'border-subtle': {
          light: '#E7E6E0',
          dark: '#222723',
        },
        // Shared architectural accents
        brand: {
          primary: '#5E9278', // Forest Sage
          'primary-hover': '#4D7A64',
          agent: '#9BCDB4',   // Soft Mint Glow
          info: '#6E96AD',    // Slate Blue
          warning: '#D19A4C', // Warm Ochre
          critical: '#B96359',// Terracotta Brick
        },
      },
      fontFamily: {
        sans: ['Plus Jakarta Sans', 'Inter', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      boxShadow: {
        'soft': '0 2px 12px -2px rgba(23, 25, 24, 0.05), 0 1px 3px -1px rgba(23, 25, 24, 0.03)',
        'soft-dark': '0 2px 16px -2px rgba(0, 0, 0, 0.35)',
        'elevated': '0 8px 30px -4px rgba(23, 25, 24, 0.08)',
        'elevated-dark': '0 8px 30px -4px rgba(0, 0, 0, 0.5)',
      }
    },
  },
  plugins: [],
}
