# Design Tokens & Styling Specification
## Project: Ledger Control — Enterprise Financial Control Tower
**Design Persona**: Enterprise Finance Terminal & Accounting Operations Infrastructure  
**Document Status**: Strict Technical Guidelines — Zero Deviations Allowed

---

## 1. Core Color Tokens

```css
:root {
  /* Surface & Canvas Hierarchy */
  --color-bg: #0F1712;                   /* Deep obsidian forest canvas */
  --color-surface: #16211C;              /* Primary terminal surface, table rows, cards */
  --color-surface-elevated: #1D2C25;     /* Modals, popovers, elevated drawers */
  --color-surface-hover: #23352D;        /* Hover states for interactive rows and items */

  /* Text & Content */
  --color-text-primary: #EDEFEA;         /* Primary ledger text, metrics, high contrast */
  --color-text-muted: #8A9A92;           /* Secondary metadata, table headers, labels */
  --color-text-disabled: #4E5D56;        /* Inactive states, disabled controls */

  /* Financial Semantics */
  --color-ledger-green: #2D6A4F;         /* Primary brand & verified/matched transactions */
  --color-ledger-green-bg: rgba(45, 106, 79, 0.15);
  --color-ledger-green-border: #2D6A4F;

  --color-ledger-gold: #C9A227;          /* Critical financial metrics, totals, key badges */
  --color-ledger-gold-bg: rgba(201, 162, 39, 0.15);
  --color-ledger-gold-border: #C9A227;

  --color-exception-amber: #D4A017;      /* Pending review, fuzzy triage, warning breaks */
  --color-exception-amber-bg: rgba(212, 160, 23, 0.15);
  --color-exception-amber-border: #D4A017;

  --color-risk-red: #DC2626;             /* Unmatched exceptions, critical breaks, rejects */
  --color-risk-red-bg: rgba(220, 38, 38, 0.15);
  --color-risk-red-border: #DC2626;

  /* Borders & Grid Separators */
  --border-width: 1px;
  --border-color-subtle: #23352D;        /* Table row dividers, subtle panel borders */
  --border-color-strong: #334B40;        /* Active card borders, inputs, focus bounds */

  /* Geometry & Elevation */
  --radius-max: 4px;                     /* Strict maximum border radius */
  --shadow-restrained: 0 4px 12px rgba(0, 0, 0, 0.4);
  --shadow-drawer: -4px 0 24px rgba(0, 0, 0, 0.6);
}
```

---

## 2. Typography System

| Token | Font Family | Size | Weight | Line Height | Application |
|---|---|---|---|---|---|
| `--font-heading` | `'Space Grotesk', sans-serif` | `18px`–`24px` | `600`, `700` | `1.2` | Page titles, module headers, modal titles |
| `--font-ui` | `'IBM Plex Sans', sans-serif` | `13px`–`14px` | `400`, `500` | `1.4` | Navigation, labels, tooltips, buttons |
| `--font-mono-financial` | `'IBM Plex Mono', monospace` | `12px`–`13px` | `500`, `600` | `1.0` | Currency figures, IDs, dates, table cells |

```css
/* Ensure Tabular Numeral Alignment Across All Financial Figures */
.num-financial,
.table-cell-amount,
.table-cell-date,
.kpi-value {
  font-family: 'IBM Plex Mono', monospace;
  font-variant-numeric: tabular-nums lining-nums;
  font-feature-settings: "tnum" 1, "zero" 1;
  letter-spacing: -0.01em;
}
```

---

## 3. Strict Prohibitions & Architectural Rules

1. **NO Purple / Indigo SaaS Default Palettes**: Exclusively use the institutional green, gold, amber, and deep obsidian forest tokens.
2. **NO Inter Font**: Use only `Space Grotesk` (Headings), `IBM Plex Sans` (UI), and `IBM Plex Mono` (Financials).
3. **NO Glassmorphism & Blurs**: Use solid, opaque surfaces (`#16211C`, `#1D2C25`) for clarity and maximum contrast.
4. **NO Excessive Gradients or Drop Shadows**: Only subtle 1px borders and restrained dark terminal shadows.
5. **NO `rounded-xl` or `rounded-2xl` Radii**: Every button, input, badge, and card is strictly bounded by `border-radius: 4px` (or `2px`).
6. **NO Cartoon Illustrations or Generic Dashboards**: Interface must feel like a precision institutional finance terminal.

---

## 4. Spacing & Density Scale

```css
--space-1: 4px;    /* Micro-padding, badge insets */
--space-2: 8px;    /* Button horizontal gaps, tight cell margins */
--space-3: 12px;   /* Standard table padding, input insets */
--space-4: 16px;   /* Card internal padding, section margins */
--space-6: 24px;   /* Module gutters, terminal panel separations */
```

---

## 5. Explicit Text Overflow & Layout Resilience Rules

### 5.1 Long Financial Values & Amounts
Financial figures must **never wrap or break across lines**:
```css
.table-cell-amount {
  font-family: 'IBM Plex Mono', monospace;
  white-space: nowrap;
  text-align: right;
  font-variant-numeric: tabular-nums;
  min-width: 110px;
}
```

### 5.2 Long Transaction Descriptions
Descriptions must truncate cleanly with an ellipsis and display full text on hover/drawer:
```css
.table-cell-description {
  max-width: 280px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  word-break: break-all;
}

@media (min-width: 1440px) {
  .table-cell-description {
    max-width: 400px;
  }
}
```

### 5.3 External Reference Codes & Transaction IDs
```css
.table-cell-reference {
  font-family: 'IBM Plex Mono', monospace;
  max-width: 160px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--color-text-muted);
}
```

### 5.4 Responsive Table Container
Tables must retain horizontal scrolling integrity without clipping or expanding the parent layout:
```css
.table-container-responsive {
  width: 100%;
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
  border: 1px solid var(--border-color-subtle);
  border-radius: var(--radius-max);
  background-color: var(--color-surface);
}

.table-container-responsive table {
  width: 100%;
  border-collapse: collapse;
  table-layout: fixed;
}
```

### 5.5 AI Explanations & Multiline Notes in Drawer
```css
.drawer-explanation-text {
  font-family: 'IBM Plex Sans', sans-serif;
  font-size: 13px;
  line-height: 1.5;
  color: var(--color-text-primary);
  white-space: normal;
  overflow-wrap: break-word;
  word-wrap: break-word;
  hyphens: auto;
}
```
