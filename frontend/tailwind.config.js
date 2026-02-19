/** @type {import('tailwindcss').Config} */
module.exports = {
    darkMode: ["class"],
    content: [
        "./src/**/*.{js,jsx,ts,tsx}",
        "./public/index.html"
    ],
    theme: {
        extend: {
            fontFamily: {
                'syne': ['Syne', 'sans-serif'],
                'dm': ['DM Sans', 'sans-serif'],
                'mono': ['JetBrains Mono', 'monospace'],
            },
            colors: {
                background: '#FDFBF7',
                foreground: '#050505',
                primary: {
                    DEFAULT: '#FF2E63',
                    foreground: '#FFFFFF',
                },
                secondary: {
                    DEFAULT: '#252A34',
                    foreground: '#FFFFFF',
                },
                accent: {
                    DEFAULT: '#CCFF00',
                    foreground: '#000000',
                },
                muted: {
                    DEFAULT: '#EAEAEA',
                    foreground: '#666666',
                },
                destructive: {
                    DEFAULT: '#FF0000',
                    foreground: '#FFFFFF',
                },
                success: '#00CC66',
                warning: '#FFCC00',
                border: '#000000',
                input: '#FFFFFF',
                ring: '#000000',
                card: {
                    DEFAULT: '#FFFFFF',
                    foreground: '#050505',
                },
                popover: {
                    DEFAULT: '#FFFFFF',
                    foreground: '#050505',
                },
            },
            borderRadius: {
                lg: '12px',
                md: '8px',
                sm: '4px',
                full: '9999px',
            },
            boxShadow: {
                'brutal': '4px 4px 0px 0px #000000',
                'brutal-lg': '8px 8px 0px 0px #000000',
                'brutal-xl': '12px 12px 0px 0px #000000',
                'brutal-hover': '6px 6px 0px 0px #000000',
                'brutal-active': '0px 0px 0px 0px #000000',
            },
            keyframes: {
                'slide-up': {
                    '0%': { opacity: '0', transform: 'translateY(30px)' },
                    '100%': { opacity: '1', transform: 'translateY(0)' },
                },
                'fade-in': {
                    '0%': { opacity: '0' },
                    '100%': { opacity: '1' },
                },
                'bounce-soft': {
                    '0%, 100%': { transform: 'translateY(0)' },
                    '50%': { transform: 'translateY(-10px)' },
                },
                'pulse-slow': {
                    '0%, 100%': { transform: 'scale(1)' },
                    '50%': { transform: 'scale(1.05)' },
                },
                'match-pop': {
                    '0%': { transform: 'scale(0)', opacity: '0' },
                    '50%': { transform: 'scale(1.2)' },
                    '100%': { transform: 'scale(1)', opacity: '1' },
                },
            },
            animation: {
                'slide-up': 'slide-up 0.5s ease-out forwards',
                'fade-in': 'fade-in 0.3s ease-out forwards',
                'bounce-soft': 'bounce-soft 2s ease-in-out infinite',
                'pulse-slow': 'pulse-slow 3s ease-in-out infinite',
                'match-pop': 'match-pop 0.5s cubic-bezier(0.175, 0.885, 0.32, 1.275) forwards',
            },
        },
    },
    plugins: [require("tailwindcss-animate")],
};
