/**
 * LEDGER CONTROL — Typed Design Tokens
 * ──────────────────────────────────────
 * TypeScript-accessible design tokens for the authenticated dark theme.
 * Mirrors the CSS custom properties defined in theme.css and provides
 * type-safe access for Recharts, inline styles, and component logic.
 */

// ── Core Surfaces ───────────────────────────────────────
export const surface = {
  bg: "#0D0D0F",
  base: "#141417",
  secondary: "#19191D",
  elevated: "#1E1E23",
  hover: "#25252B",
  active: "#2C2C34",
} as const;

// ── Borders ─────────────────────────────────────────────
export const border = {
  default: "#303038",
  strong: "#44444F",
  subtle: "rgba(48, 48, 56, 0.6)",
} as const;

// ── Typography Colors ───────────────────────────────────
export const text = {
  primary: "#F5F5F7",
  secondary: "#A7A7B0",
  muted: "#707079",
  faint: "#4E4E57",
} as const;

// ── Brand Accent (Violet) ───────────────────────────────
export const accent = {
  base: "#A855F7",
  hover: "#B66CFF",
  soft: "rgba(168, 85, 247, 0.14)",
  muted: "rgba(168, 85, 247, 0.08)",
  light: "#C084FC",
} as const;

// Alias for backward compatibility
export const primary = accent;

// ── Semantic Status ─────────────────────────────────────
export const status = {
  success: "#22C55E",
  successSoft: "rgba(34, 197, 94, 0.12)",
  warning: "#F59E0B",
  warningSoft: "rgba(245, 158, 11, 0.12)",
  danger: "#EF4444",
  dangerSoft: "rgba(239, 68, 68, 0.12)",
  info: "#60A5FA",
  infoSoft: "rgba(96, 165, 250, 0.12)",
} as const;

// ── Chart Palette ───────────────────────────────────────
export const chart = {
  palette: [
    "#A855F7", // violet
    "#22C55E", // green
    "#60A5FA", // blue
    "#F59E0B", // gold / amber
    "#EF4444", // red
    "#38BDF8", // sky
  ] as const,
  get: (index: number): string => chart.palette[index % chart.palette.length] as string,
} as const;

// ── Shadows ─────────────────────────────────────────────
export const shadow = {
  sm: "0 1px 2px rgba(0, 0, 0, 0.4)",
  md: "0 4px 12px rgba(0, 0, 0, 0.35)",
  lg: "0 12px 32px rgba(0, 0, 0, 0.5)",
  glow: "0 0 24px rgba(168, 85, 247, 0.12)",
} as const;

// ── Layout & Radii ──────────────────────────────────────
export const layout = {
  sidebarWidth: 240,
  topbarHeight: 54,
  radiusSm: 4,
  radius: 6,
  radiusLg: 8,
  maxContentWidth: "88rem",
  buttonHeight: 34,
  inputHeight: 34,
} as const;

// ── Typography Stacks ───────────────────────────────────
export const fonts = {
  heading:
    '"Space Grotesk", "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
  body: '"Inter", "IBM Plex Sans", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
  mono: '"IBM Plex Mono", "JetBrains Mono", ui-monospace, SFMono-Regular, Menlo, monospace',
} as const;

// ── Responsive Breakpoints ──────────────────────────────
export const breakpoints = {
  sm: 375,
  mobile: 390,
  tablet: 768,
  desktop: 1024,
  wide: 1280,
  ultra: 1440,
} as const;

// ── Complete Token Export ────────────────────────────────
export const tokens = {
  surface,
  border,
  text,
  accent,
  primary,
  status,
  chart,
  shadow,
  layout,
  fonts,
  breakpoints,
} as const;

export default tokens;
