import AuthGuard from "@/components/AuthGuard";

export default function DriveCrawlLayout({ children }: { children: React.ReactNode }) {
  return <AuthGuard>{children}</AuthGuard>;
}
