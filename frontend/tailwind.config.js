/**
 * Tailwind CSS configuration for Table Queue
 * Status colors from _docs/ui.md section 2
 */

/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        // Status colors from _docs/ui.md section 2
        WAITING: '#3B82F6',
        CALLED: '#EA580C',
        SEATED: '#16A34A',
        NO_SHOW: '#DC2626',
        CANCELLED: '#64748B',
        DONE: '#166534',
        // Base tokens
        'bg-guest': '#FFFBF5',
        'bg-staff': '#F8FAFC',
        'text-primary': '#1E293B',
        'text-secondary': '#64748B',
        'border-default': '#E2E8F0',
        primary: '#EA580C',
        'primary-hover': '#C2410C',
        // Table status colors
        AVAILABLE: '#16A34A',
        OCCUPIED: '#EA580C',
        CLEANING: '#F59E0B',
      },
      fontFamily: {
        sans: ['Inter', 'Noto Sans TC', 'sans-serif'],
      },
      borderRadius: {
        '2xl': '1rem',
        '3xl': '1.5rem',
      },
    },
  },
  plugins: [],
};
