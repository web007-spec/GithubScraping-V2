import type { GitHubUser } from "./types";

/** Client-side country rollup (Community alternative to pivot mode). */
export type CountrySummaryRow = {
  id: number;
  login: string;
  name: string;
  country: string;
  email: string;
  email_source: string;
  followers: number;
  following: number;
  public_repos: number;
  bio: string;
  company: string;
  location: string;
  last_scraped_at: string;
  _summaryCount: number;
  _withEmail: number;
};

export function buildCountrySummaryRows(users: GitHubUser[]): CountrySummaryRow[] {
  const byCountry = new Map<string, GitHubUser[]>();
  for (const u of users) {
    const key = u.country?.trim() || "Unknown";
    if (!byCountry.has(key)) byCountry.set(key, []);
    byCountry.get(key)!.push(u);
  }

  return [...byCountry.entries()]
    .sort((a, b) => b[1].length - a[1].length)
    .map(([country, list]) => {
      const withEmail = list.filter((u) => u.email).length;
      const avg = (field: keyof GitHubUser) => {
        const nums = list.map((u) => Number(u[field]) || 0);
        return nums.length
          ? Math.round(nums.reduce((a, b) => a + b, 0) / nums.length)
          : 0;
      };
      return {
        id: -Math.abs(country.split("").reduce((h, c) => h + c.charCodeAt(0), 0)),
        login: `${list.length} users`,
        name: `${withEmail} with email`,
        country,
        email: withEmail > 0 ? `${withEmail} addresses` : "",
        email_source: "summary",
        followers: avg("followers"),
        following: avg("following"),
        public_repos: avg("public_repos"),
        bio: `Total: ${list.length}`,
        company: "",
        location: country,
        last_scraped_at: "",
        _summaryCount: list.length,
        _withEmail: withEmail,
      };
    });
}
