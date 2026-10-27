"use client";

import Navbar from "@/components/Navbar";

export default function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="app-shell min-h-screen">
      <Navbar />
      <main className="app-main mx-auto max-w-[1600px] px-4 py-6 sm:px-6">{children}</main>
    </div>
  );
}
