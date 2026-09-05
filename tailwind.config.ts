import type { Config } from 'tailwindcss';

export default {
  content: ['./app/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        ink: '#080b0e',
        panel: '#11171e',
        edge: '#1e2934',
        muted: '#7f8f9e',
        open: '#22d3a5',
        mid: '#f2b544',
        tight: '#f2545b',
      },
      fontFamily: {
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'Consolas', 'monospace'],
      },
    },
  },
  plugins: [],
} satisfies Config;
