"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import AuthLayout, { AuthTabs } from "@/components/AuthLayout";
import { LoadingDots } from "@/components/LoadingState";
import { formatAuthError, getSupabaseConfigError } from "@/lib/auth";
import { loginWithApi } from "@/lib/auth-session";
import { AUTH_TIMEOUT_MS, withAuthTimeout } from "@/lib/auth-timeout";
import { useMongoStorage } from "@/lib/database-storage";
import { createClient } from "@/lib/supabase";

export default function LoginPage() {
  const router = useRouter();
  const configError = getSupabaseConfigError();

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const err = params.get("error");
    if (err === "not_admin") {
      setError("Your account is not an admin. Register or ask the server owner to grant access.");
    } else if (err) {
      setError(decodeURIComponent(err));
    }
  }, []);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (configError) {
      setError(configError);
      return;
    }
    setLoading(true);
    setError("");
    try {
      if (useMongoStorage) {
        const data = await loginWithApi(email, password);
        if (data.user?.role !== "admin") {
          setError("Signed in, but this account is not an admin.");
          return;
        }
        router.push("/");
        router.refresh();
        return;
      }

      const supabase = createClient();
      const { error: err } = await supabase.auth.signInWithPassword({
        email,
        password,
      });
      if (err) {
        setError(formatAuthError(err.message));
        return;
      }
      try {
        await withAuthTimeout(supabase.auth.refreshSession(), AUTH_TIMEOUT_MS, "Session refresh");
      } catch {
        /* continue with sign-in session */
      }
      const { data: userData } = await withAuthTimeout(
        supabase.auth.getUser(),
        AUTH_TIMEOUT_MS,
        "User check"
      );
      const role = userData.user?.app_metadata?.role;
      if (role !== "admin") {
        setError(
          "Signed in, but this account is not an admin. Use Register or ask the server owner to set role=admin."
        );
        return;
      }
      router.push("/");
      router.refresh();
    } catch (err) {
      setError(
        err instanceof Error
          ? formatAuthError(err.message)
          : "Failed to reach the API. Check that the backend is running."
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthLayout
      title="Welcome back"
      subtitle="Sign in to manage GitHub scraping and Google Drive"
      footer={
        <div className="space-y-2 text-github-light">
          <p>
            No account?{" "}
            <Link href="/register" className="font-medium text-accent hover:underline">
              Create one
            </Link>
          </p>
          <p>
            <Link href="/explore/drive" className="font-medium text-accent hover:underline">
              Browse indexed Google Drive
            </Link>{" "}
            (public, no sign-in)
          </p>
        </div>
      }
    >
      <AuthTabs active="login" />
      {configError && <p className="alert-info mb-4">{configError}</p>}
      {error && <p className="alert-error mb-4">{error}</p>}
      <form onSubmit={handleSubmit}>
        <label className="label">Email</label>
        <input
          type="email"
          className="input mb-4"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          autoComplete="email"
          required
        />
        <label className="label">Password</label>
        <input
          type="password"
          className="input mb-6"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete="current-password"
          required
        />
        <button type="submit" className="btn-primary w-full" disabled={loading}>
          {loading ? <LoadingDots label="Signing in" /> : "Sign in"}
        </button>
      </form>
    </AuthLayout>
  );
}
