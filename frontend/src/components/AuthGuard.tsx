"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { fetchCurrentUser, getAccessToken } from "@/lib/auth-session";
import { sessionIsValid, readAuthSession } from "@/lib/auth-token";
import { useMongoStorage } from "@/lib/database-storage";
import { AUTH_TIMEOUT_MS, withAuthTimeout } from "@/lib/auth-timeout";
import { createClient } from "@/lib/supabase";
import LoadingState from "./LoadingState";
import ModuleSubnav from "./ModuleSubnav";
import Navbar from "./Navbar";

export default function AuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [ready, setReady] = useState(false);
  const [message, setMessage] = useState("Loading...");

  useEffect(() => {
    let cancelled = false;

    async function checkMongo() {
      const session = readAuthSession();
      if (!sessionIsValid(session)) {
        router.replace("/login");
        return;
      }
      const user = await fetchCurrentUser();
      if (cancelled) return;
      if (!user || user.role !== "admin") {
        router.replace("/login?error=not_admin");
        return;
      }
      setReady(true);
    }

    async function checkSupabase() {
      const supabase = createClient();

      try {
        const { data: sessionData, error: sessionError } = await withAuthTimeout(
          supabase.auth.getSession(),
          AUTH_TIMEOUT_MS,
          "Session check"
        );

        if (cancelled) return;

        if (sessionError || !sessionData.session?.user) {
          router.replace("/login");
          return;
        }

        const expiresAt = sessionData.session.expires_at ?? 0;
        const now = Math.floor(Date.now() / 1000);
        if (expiresAt - now < 120) {
          try {
            await withAuthTimeout(
              supabase.auth.refreshSession(),
              AUTH_TIMEOUT_MS,
              "Session refresh"
            );
          } catch {
            /* use existing session if refresh fails on LAN */
          }
        }

        const { data, error } = await withAuthTimeout(
          supabase.auth.getUser(),
          AUTH_TIMEOUT_MS,
          "User check"
        );

        if (cancelled) return;

        if (error || !data.user) {
          router.replace("/login");
          return;
        }

        if (data.user.app_metadata?.role !== "admin") {
          router.replace("/login?error=not_admin");
          return;
        }

        setReady(true);
      } catch {
        if (cancelled) return;
        setMessage("Auth check failed. Redirecting to sign in...");
        router.replace("/login");
      }
    }

    async function check() {
      if (useMongoStorage) {
        const token = await getAccessToken();
        if (!token) {
          router.replace("/login");
          return;
        }
        await checkMongo();
        return;
      }
      await checkSupabase();
    }

    void check();

    return () => {
      cancelled = true;
    };
  }, [router]);

  if (!ready) {
    return (
      <div className="app-shell flex min-h-screen items-center justify-center">
        <LoadingState
          variant="card"
          title={message}
          detail="Verifying your session and preparing the workspace."
        />
      </div>
    );
  }

  return (
    <div className="app-shell min-h-screen">
      <Navbar />
      <ModuleSubnav />
      <main className="app-main mx-auto max-w-[1600px] px-4 py-6 sm:px-6">{children}</main>
    </div>
  );
}
