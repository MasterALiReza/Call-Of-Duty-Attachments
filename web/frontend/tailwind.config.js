/** @type {import('tailwindcss').Config} */

function withOpacity(variableName) {
  return ({ opacityValue }) => {
    if (opacityValue !== undefined) {
      return `rgb(var(${variableName}) / ${opacityValue})`;
    }
    return `rgb(var(${variableName}))`;
  };
}

export default {
  darkMode: ['class', '[data-theme="dark"]'],
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        background: withOpacity('--color-bg-main'),
        card: {
          DEFAULT: withOpacity('--color-card-bg'),
          surface: withOpacity('--color-card-surface'),
          hover: withOpacity('--color-card-hover'),
        },
        border: {
          DEFAULT: withOpacity('--color-border-main'),
          subtle: withOpacity('--color-border-subtle'),
          highlight: withOpacity('--color-border-highlight'),
        },
        primary: {
          DEFAULT: withOpacity('--color-primary'),
          hover: withOpacity('--color-primary-hover'),
          active: withOpacity('--color-primary-active'),
          text: withOpacity('--color-primary-text'),
          glow: 'var(--primary-glow)',
        },
        secondary: {
          DEFAULT: withOpacity('--color-secondary'),
          hover: withOpacity('--color-secondary-hover'),
          text: withOpacity('--color-secondary-text'),
        },
        accent: {
          DEFAULT: withOpacity('--color-accent'),
          hover: withOpacity('--color-accent-hover'),
          text: withOpacity('--color-accent-text'),
          glow: 'var(--accent-glow)',
        },
        danger: {
          DEFAULT: '#ef4444',
          hover: '#dc2626',
          surface: 'rgba(239, 68, 68, 0.12)',
        },
        mainText: {
          DEFAULT: withOpacity('--color-text-main'),
          muted: withOpacity('--color-text-muted'),
          subtle: withOpacity('--color-text-subtle'),
        },
      },
      fontFamily: {
        sans: ['Vazirmatn', 'system-ui', '-apple-system', 'Segoe UI', 'Roboto', 'sans-serif'],
        mono: ['Vazirmatn', 'system-ui', '-apple-system', 'Segoe UI', 'Roboto', 'sans-serif'],
      },
      boxShadow: {
        'glow-primary': '0 0 20px -3px var(--primary-glow)',
        'glow-accent': '0 0 20px -3px var(--accent-glow)',
        'card-elevated': 'var(--shadow-card-elevated)',
      }
    },
  },
  plugins: [],
}
