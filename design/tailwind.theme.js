/**
 * Harmony-v1 Inspired Tailwind Theme Extension
 * 
 * This configuration extends Tailwind CSS with colors and typography
 * from the harmony-v1 backup project (Wizarr-based theme).
 * 
 * Usage: Import and merge this into your main tailwind.config.js
 * 
 * Example:
 * ```js
 * const harmonyTheme = require('./design/tailwind.theme.js');
 * 
 * module.exports = {
 *   theme: {
 *     extend: {
 *       ...harmonyTheme.extend
 *     }
 *   }
 * }
 * ```
 */

module.exports = {
  extend: {
    colors: {
      // Harmony brand colors
      harmony: {
        primary: {
          DEFAULT: '#fe4155',
          hover: '#982633',
        },
        secondary: {
          DEFAULT: '#533c5b',
          hover: '#332538',
        },
        blue: {
          primary: '#3b82f6',
          secondary: '#1d4ed8',
        },
      },
      
      // Override primary with Harmony colors
      'harmony-primary': {
        50: '#fff1f2',
        100: '#ffe4e6',
        200: '#fecdd3',
        300: '#fda4af',
        400: '#fb7185',
        500: '#fe4155',  // Main Harmony primary
        600: '#982633',  // Harmony hover
        700: '#be123c',
        800: '#9f1239',
        900: '#881337',
      },
      
      // Override secondary with Harmony colors
      'harmony-secondary': {
        50: '#faf5ff',
        100: '#f3e8ff',
        200: '#e9d5ff',
        300: '#d8b4fe',
        400: '#a78bfa',
        500: '#533c5b',  // Main Harmony secondary
        600: '#332538',  // Harmony hover
        700: '#6b21a8',
        800: '#581c87',
        900: '#3b0764',
      },
    },
    
    fontFamily: {
      // Inter font with system fallbacks
      harmony: [
        'Inter',
        '-apple-system',
        'BlinkMacSystemFont',
        'Segoe UI',
        'system-ui',
        'sans-serif',
      ],
    },
    
    fontSize: {
      // Harmony typography scale
      'harmony-xs': ['0.75rem', { lineHeight: '1.5' }],
      'harmony-sm': ['0.875rem', { lineHeight: '1.5' }],
      'harmony-base': ['1rem', { lineHeight: '1.5' }],
      'harmony-lg': ['1.125rem', { lineHeight: '1.5' }],
      'harmony-xl': ['1.25rem', { lineHeight: '1.25' }],
      'harmony-2xl': ['1.5rem', { lineHeight: '1.25' }],
      'harmony-3xl': ['1.875rem', { lineHeight: '1.25' }],
      'harmony-4xl': ['2.25rem', { lineHeight: '1.25' }],
    },
    
    spacing: {
      // Harmony spacing scale
      'harmony-xs': '0.25rem',
      'harmony-sm': '0.5rem',
      'harmony-md': '1rem',
      'harmony-lg': '1.5rem',
      'harmony-xl': '2rem',
      'harmony-2xl': '2.5rem',
    },
    
    borderRadius: {
      // Harmony border radius
      'harmony-sm': '0.25rem',
      'harmony-md': '0.5rem',
      'harmony-lg': '0.75rem',
      'harmony-xl': '1rem',
    },
    
    boxShadow: {
      // Harmony shadows
      'harmony-sm': '0 1px 2px 0 rgba(0, 0, 0, 0.05)',
      'harmony-md': '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)',
      'harmony-lg': '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)',
      'harmony-xl': '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)',
    },
    
    transitionDuration: {
      // Harmony transitions
      'harmony-fast': '150ms',
      'harmony-normal': '200ms',
      'harmony-slow': '300ms',
    },
  },
};
