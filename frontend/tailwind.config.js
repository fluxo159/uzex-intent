export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        bg: 'var(--bg)', s1: 'var(--s1)', s2: 'var(--s2)', s3: 'var(--s3)',
        ink: 'var(--ink)', ink2: 'var(--ink-2)', ink3: 'var(--ink-3)', mute: 'var(--mute)',
        lime: 'var(--lime)', 'lime-ink': 'var(--lime-ink)',
        lav: 'var(--lav)', 'lav-bg': 'var(--lav-bg)',
        warn: 'var(--warn)', 'warn-bg': 'var(--warn-bg)',
        bad: 'var(--bad)', line: 'var(--line)',
      },
      fontFamily: {
        sans: ['Geist', 'system-ui', '-apple-system', 'Segoe UI', 'Roboto', 'sans-serif'],
        mono: ['Geist', 'system-ui', 'sans-serif'],
      },
      borderRadius: { card: '24px', chip: '10px' },
      maxWidth: { app: '1120px', phone: '390px' },
    },
  },
  plugins: [],
}
