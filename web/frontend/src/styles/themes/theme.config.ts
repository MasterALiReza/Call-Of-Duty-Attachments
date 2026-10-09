/**
 * ─────────────────────────────────────────────────────────────────────────────
 * THEME CONFIGURATION & PALETTES METADATA
 * Type-safe access to theme tokens in TypeScript components and charts.
 * ─────────────────────────────────────────────────────────────────────────────
 */

export interface ThemeColors {
  bgMain: string;
  cardBg: string;
  cardSurface: string;
  cardHover: string;
  borderMain: string;
  borderSubtle: string;
  borderHighlight: string;
  primary: string;
  primaryHover: string;
  primaryText: string;
  secondary: string;
  accent: string;
  textMain: string;
  textMuted: string;
  textSubtle: string;
}

export const lightThemePalette: ThemeColors = {
  bgMain: '#F9F7F7',
  cardBg: '#FFFFFF',
  cardSurface: '#DBE2EF',
  cardHover: '#EBF0F8',
  borderMain: '#DBE2EF',
  borderSubtle: '#E7EDF6',
  borderHighlight: '#3F72AF',
  primary: '#3F72AF',
  primaryHover: '#315B8C',
  primaryText: '#FFFFFF',
  secondary: '#112D4E',
  accent: '#3F72AF',
  textMain: '#112D4E',
  textMuted: '#4B6584',
  textSubtle: '#798E9C',
};

export const darkThemePalette: ThemeColors = {
  bgMain: '#061822',
  cardBg: '#0A222E',
  cardSurface: '#0E2C3B',
  cardHover: '#14384B',
  borderMain: '#1A4356',
  borderSubtle: 'rgba(26, 67, 86, 0.45)',
  borderHighlight: '#7AE2CF',
  primary: '#7AE2CF',
  primaryHover: '#62C8B5',
  primaryText: '#061822',
  secondary: '#1E4E63',
  accent: '#FDEB9E',
  textMain: '#F1F5F9',
  textMuted: '#94A8B8',
  textSubtle: '#607B8E',
};

export const palettes = {
  light: lightThemePalette,
  dark: darkThemePalette,
};
