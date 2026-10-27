type ValidationErrorItem = {
  msg?: string;
  loc?: (string | number)[];
  type?: string;
};

/** Turn FastAPI/Pydantic `detail` into a single human-readable string. */
export function parseApiErrorDetail(detail: unknown, fallback = "Request failed"): string {
  if (typeof detail === "string" && detail.trim()) return detail.trim();
  if (Array.isArray(detail)) {
    const parts = detail
      .map((item) => {
        if (typeof item === "string") return item;
        const row = item as ValidationErrorItem;
        if (!row.msg) return "";
        const field = Array.isArray(row.loc) ? row.loc[row.loc.length - 1] : null;
        if (field === "password" && row.type === "string_too_short") {
          return "Password must be at least 6 characters.";
        }
        if (field === "email" && row.type === "value_error") {
          return "Enter a valid email address.";
        }
        return row.msg;
      })
      .filter(Boolean);
    if (parts.length) return parts.join(" ");
  }
  if (detail && typeof detail === "object" && "msg" in detail) {
    return String((detail as ValidationErrorItem).msg || fallback);
  }
  return fallback;
}
