"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import AuthLayout, { AuthTabs } from "@/components/AuthLayout";
import { LoadingDots } from "@/components/LoadingState";
import {
  formatAuthError,
  getSupabaseConfigError,
  registerViaServer,
} from "@/lib/auth";
import { loginWithApi } from "@/lib/auth-session";
import { useMongoStorage } from "@/lib/database-storage";
import { createClient } from "@/lib/supabase";

export default function RegisterPage() {
  const router = useRouter();
  const configError = getSupabaseConfigError();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [secret, setSecret] = useState("");
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (configError) {
      setError(configError);
      return;
    }
    if (password !== confirm) {
      setError("Passwords do not match");
      return;
    }
    if (password.length < 6) {
      setError("Password must be at least 6 characters");
      return;
    }

    setLoading(true);
    setError("");
    setInfo("");

    try {
      // Server-side registration: no confirmation email, avoids Supabase email rate limit
      await registerViaServer(email, password, secret || undefined);

      if (useMongoStorage) {
        const data = await loginWithApi(email, password);
        if (data.user?.role !== "admin") {
          setInfo("Account created. Please sign in from the login page.");
          return;
        }
        setInfo("Registration complete. Redirecting…");
        router.push("/");
        router.refresh();
        return;
      }

      const supabase = createClient();
      const { error: signInError } = await supabase.auth.signInWithPassword({
        email,
        password,
      });

      if (signInError) {
        setInfo(
          "Account created. Please go to Sign in and log in with your email and password."
        );
        return;
      }

      await supabase.auth.refreshSession();
      const { data: userData } = await supabase.auth.getUser();
      if (userData.user?.app_metadata?.role !== "admin") {
        setInfo(
          "Account created. Please sign out, sign in again, or wait a moment and refresh."
        );
        return;
      }

      setInfo("Registration complete. Redirecting…");
      router.push("/");
      router.refresh();
    } catch (err) {
      setError(
        err instanceof Error
          ? formatAuthError(err.message)
          : "Registration failed. Is the backend running?"
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthLayout
      title="Create account"
      subtitle="Create an admin account for GitHub scraping and Google Drive"
      footer={
        <p className="text-github-light">
          Already have an account?{" "}
          <Link href="/login" className="font-medium text-accent hover:underline">
            Sign in
          </Link>
        </p>
      }
    >
      <AuthTabs active="register" />
      {configError && <p className="alert-info mb-4">{configError}</p>}
      {error && <p className="alert-error mb-4">{error}</p>}
      {info && <p className="alert-success mb-4">{info}</p>}
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
          className="input mb-4"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete="new-password"
          minLength={6}
          required
        />
        <label className="label">Confirm password</label>
        <input
          type="password"
          className="input mb-4"
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
          autoComplete="new-password"
          minLength={6}
          required
        />
        <label className="label">
          Registration secret{" "}
          <span className="font-normal text-github-muted">(only if your server requires it)</span>
        </label>
        <input
          type="password"
          className="input mb-6"
          value={secret}
          onChange={(e) => setSecret(e.target.value)}
          placeholder="Leave empty unless configured"
        />
        <button type="submit" className="btn-primary w-full" disabled={loading}>
          {loading ? <LoadingDots label="Creating account" /> : "Register"}
        </button>
      </form>
      <p className="mt-4 text-xs text-github-light">
        Accounts are created on your server without sending a confirmation email.
      </p>
    </AuthLayout>
  );
}
