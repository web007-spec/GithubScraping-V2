import { themeMaterial } from "ag-grid-community";

/**
 * Dark admin grid theme tuned for dense server-paged operations.
 */
export const githubUsersGridTheme = themeMaterial.withParams({
  primaryColor: "#38bdf8",
  accentColor: "#22d3ee",
  backgroundColor: "#0b1220",
  foregroundColor: "#dbeafe",
  headerBackgroundColor: "#111827",
  headerTextColor: "#93a4b8",
  borderColor: "#253244",
  oddRowBackgroundColor: "#0f172a",
  rowHoverColor: "rgba(56, 189, 248, 0.08)",
  selectedRowBackgroundColor: "rgba(56, 189, 248, 0.14)",
  rangeSelectionBorderColor: "#38bdf8",
  checkboxCheckedBackgroundColor: "#38bdf8",
  fontFamily: [
    { googleFont: "Roboto" },
    "Helvetica",
    "Arial",
    "sans-serif",
  ],
  fontSize: 13,
  headerFontSize: 13,
  spacing: 4,
  borderRadius: 2,
  wrapperBorderRadius: 2,
  wrapperBorder: true,
  cellHorizontalPadding: 16,
  headerHeight: 48,
  rowHeight: 42,
  listItemHeight: 40,
});

export const AG_GRID_MATERIAL = {
  primary: "#38bdf8",
  accent: "#22d3ee",
  headerBg: "#111827",
  border: "#253244",
  pageBg: "#070b12",
} as const;
