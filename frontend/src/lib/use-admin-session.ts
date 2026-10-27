"use client";

import { useEffect, useState } from "react";
import { fetchCurrentUser, getAccessToken } from "@/lib/auth-session";
import { sessionIsValid, readAuthSession } from "@/lib/auth-token";
import { useMongoStorage } from "@/lib/database-storage";
import { createClient } from "@/lib/supabase";

export function useAdminSession() {
  const [isAdmin, setIsAdmin] = useState(false);
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      if (useMongoStorage) {
        const session = readAuthSession();
        if (!sessionIsValid(session)) {
          if (!cancelled) {
            setIsAdmin(false);
            setChecking(false);
          }
          return;
        }
        const user = await fetchCurrentUser();
        if (!cancelled) {
          setIsAdmin(user?.role === "admin");
          setChecking(false);
        }
        return;
      }

      createClient()
        .auth.getSession()
        .then(({ data }) => {
          if (cancelled) return;
          const role = data.session?.user?.app_metadata?.role;
          setIsAdmin(role === "admin");
        })
        .finally(() => {
          if (!cancelled) setChecking(false);
        });
    }

    void load();

    return () => {
      cancelled = true;
    };
  }, []);

  return { isAdmin, checking };
}
