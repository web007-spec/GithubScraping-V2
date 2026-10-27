from __future__ import annotations

import os


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


DEFAULT_COUNTRIES = [
    "US", "India", "UK", "Germany", "Canada", "Japan", "France", "Brazil",
    "Australia", "Netherlands", "Sweden", "Spain", "Italy", "Poland",
    "Ukraine", "Russia", "China", "Singapore", "Switzerland",
    "Norway", "Denmark", "Finland", "Belgium", "Austria", "Ireland",
    "United Arab Emirates", "Saudi Arabia", "Qatar", "Israel", "Mexico",
    "Argentina", "Chile", "Colombia", "Peru", "Indonesia", "Philippines",
    "Vietnam", "Thailand", "Malaysia", "Pakistan", "Bangladesh", "Sri Lanka",
    "Nepal", "Nigeria", "South Africa", "Egypt", "Kenya", "Morocco", "Turkey",
    "Czech Republic", "Portugal", "Romania", "Greece", "Hungary", "Bulgaria",
    "Serbia", "Croatia", "Slovakia", "Slovenia", "Lithuania", "Estonia",
    "Latvia", "New Zealand", "Taiwan", "Hong Kong",
]

COUNTRY_LOCATION_TERMS: dict[str, str] = {
    "US": "United States",
    "India": "India",
    "UK": "United Kingdom",
    "Germany": "Germany",
    "Canada": "Canada",
    "Japan": "Japan",
    "France": "France",
    "Brazil": "Brazil",
    "Australia": "Australia",
    "Netherlands": "Netherlands",
    "Sweden": "Sweden",
    "Spain": "Spain",
    "Italy": "Italy",
    "Poland": "Poland",
    "Ukraine": "Ukraine",
    "Russia": "Russia",
    "China": "China",
    "Singapore": "Singapore",
    "Switzerland": "Switzerland",
    "Norway": "Norway",
    "Denmark": "Denmark",
    "Finland": "Finland",
    "Belgium": "Belgium",
    "Austria": "Austria",
    "Ireland": "Ireland",
    "United Arab Emirates": "United Arab Emirates",
    "Saudi Arabia": "Saudi Arabia",
    "Qatar": "Qatar",
    "Indonesia": "Indonesia",
    "Nigeria": "Nigeria",
    "Israel": "Israel",
    "Mexico": "Mexico",
    "Argentina": "Argentina",
    "Chile": "Chile",
    "Colombia": "Colombia",
    "Peru": "Peru",
    "Philippines": "Philippines",
    "Vietnam": "Vietnam",
    "Thailand": "Thailand",
    "Malaysia": "Malaysia",
    "Turkey": "Turkey",
    "Czech Republic": "Czech Republic",
    "Portugal": "Portugal",
    "Romania": "Romania",
    "Pakistan": "Pakistan",
    "Bangladesh": "Bangladesh",
    "Sri Lanka": "Sri Lanka",
    "Nepal": "Nepal",
    "South Africa": "South Africa",
    "Egypt": "Egypt",
    "Kenya": "Kenya",
    "Morocco": "Morocco",
    "Greece": "Greece",
    "Hungary": "Hungary",
    "Bulgaria": "Bulgaria",
    "Serbia": "Serbia",
    "Croatia": "Croatia",
    "Slovakia": "Slovakia",
    "Slovenia": "Slovenia",
    "Lithuania": "Lithuania",
    "Estonia": "Estonia",
    "Latvia": "Latvia",
    "New Zealand": "New Zealand",
    "Taiwan": "Taiwan",
    "Hong Kong": "Hong Kong",
}

# Fewer buckets = faster runs; still covers most users
DEFAULT_FOLLOWER_BUCKETS = ["0..99", "100..999", "1000..9999"]
DEFAULT_DATE_BUCKETS = [
    "2008-01-01..2014-12-31",
    "2015-01-01..2020-12-31",
    "2021-01-01..2025-12-31",
]

SEARCH_MAX_RESULTS = 1000
PER_PAGE = 100
UPSERT_BATCH_SIZE = 100
SKIP_SCRAPE_HOURS = 24
REQUEST_DELAY_MIN = _env_float("GITHUB_SCRAPER_REQUEST_DELAY_MIN", 0.12)
REQUEST_DELAY_MAX = _env_float("GITHUB_SCRAPER_REQUEST_DELAY_MAX", 0.35)
PROFILE_FETCH_WORKERS = _env_int("GITHUB_SCRAPER_PROFILE_WORKERS", 6)
PROFILE_ENRICH_CHUNK = _env_int("GITHUB_SCRAPER_PROFILE_CHUNK", 20)
GRAPHQL_BATCH_SIZE = _env_int("GITHUB_SCRAPER_GRAPHQL_BATCH", 25)
RECENT_SKIP_MAX_LOGINS = _env_int("GITHUB_SCRAPER_RECENT_SKIP_MAX", 3000)
RATE_LIMIT_THROTTLE_BELOW = 80
GITHUB_API = "https://api.github.com"
