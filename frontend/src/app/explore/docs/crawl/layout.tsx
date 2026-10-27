import AuthGuard from "@/components/AuthGuard";

export default function DocsCrawlLayout({ children }: { children: React.ReactNode }) {
  return <AuthGuard>{children}</AuthGuard>;
}
