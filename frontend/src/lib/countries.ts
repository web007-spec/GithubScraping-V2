export const DEFAULT_COUNTRIES = [
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
];

export const COUNTRY_PRESETS = [
  {
    id: "developer-hubs",
    label: "Developer hubs",
    countries: [
      "US", "India", "UK", "Germany", "Canada", "Japan", "France", "Brazil",
      "Australia", "Netherlands", "Poland", "Ukraine", "China",
      "Singapore", "Israel", "Indonesia", "Philippines", "Vietnam", "Pakistan",
      "Bangladesh", "Nigeria", "South Africa", "Turkey", "Romania",
    ],
  },
  {
    id: "client-markets",
    label: "Client markets",
    countries: [
      "US", "UK", "Germany", "Canada", "Japan", "France", "Australia",
      "Netherlands", "Sweden", "Switzerland", "Norway", "Denmark", "Finland",
      "Belgium", "Austria", "Ireland", "United Arab Emirates", "Saudi Arabia",
      "Qatar", "Singapore", "Israel", "New Zealand",
    ],
  },
  {
    id: "wealthy-markets",
    label: "Wealthy markets",
    countries: [
      "US", "UK", "Germany", "Canada", "Japan", "Australia", "Netherlands",
      "Sweden", "Switzerland", "Norway", "Denmark", "Finland", "Belgium",
      "Austria", "Ireland", "United Arab Emirates", "Saudi Arabia", "Qatar",
      "Singapore", "Taiwan", "Hong Kong", "New Zealand",
    ],
  },
  {
    id: "global-balanced",
    label: "Global balanced",
    countries: [
      "US", "India", "UK", "Germany", "Canada", "Japan", "France", "Brazil",
      "Australia", "Netherlands", "Singapore", "Switzerland",
      "United Arab Emirates", "Israel", "Mexico", "Argentina", "Colombia",
      "Indonesia", "Philippines", "Vietnam", "Malaysia", "Pakistan",
      "Bangladesh", "Nigeria", "South Africa", "Egypt", "Turkey", "Poland",
      "Ukraine", "Romania",
    ],
  },
] as const;

export const FOLLOWER_BUCKETS = ["0..99", "100..999", "1000..9999"];

export const DATE_BUCKETS = [
  "2008-01-01..2014-12-31",
  "2015-01-01..2020-12-31",
  "2021-01-01..2025-12-31",
];
