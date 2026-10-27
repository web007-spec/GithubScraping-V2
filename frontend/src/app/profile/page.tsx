import AuthGuard from "@/components/AuthGuard";
import AccountProfilePage from "@/components/AccountProfilePage";

export default function ProfilePage() {
  return (
    <AuthGuard>
      <AccountProfilePage />
    </AuthGuard>
  );
}
