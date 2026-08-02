/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        friday: {
          bg: '#040404',
          surface: '#0a0f1e',
          panel: 'rgba(6,9,20,0.7)',
          border: 'rgba(0,180,255,0.12)',
          cyan: '#00b4ff',
          blue: '#0066ff',
          accent: '#00e5ff',
          glow: 'rgba(0,180,255,0.4)',
          text: '#e0f4ff',
          muted: 'rgba(180,220,255,0.5)',
          danger: '#ff3366',
          success: '#00ff88',
          warning: '#ffaa00',
        },
      },
      fontFamily: {
        sans: ['Space Grotesk', 'Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
      animation: {
        'pulse-slow': 'pulse 3s ease-in-out infinite',
        'spin-slow': 'spin 12s linear infinite',
        'float': 'float 6s ease-in-out infinite',
      },
      keyframes: {
        float: {
          '0%, 100%': { transform: 'translateY(0px)' },
          '50%': { transform: 'translateY(-8px)' },
        },
      },
      boxShadow: {
        'glow-cyan': '0 0 18px rgba(0,180,255,0.35), 0 0 40px rgba(0,180,255,0.15)',
        'glow-sm': '0 0 10px rgba(0,180,255,0.25)',
        panel: '0 8px 32px rgba(0,0,0,0.65), inset 0 1px 0 rgba(255,255,255,0.04)',
      },
    },
  },
  plugins: [],
};
