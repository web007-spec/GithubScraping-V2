import ModuleSubnav from "@/components/ModuleSubnav";
import Navbar from "@/components/Navbar";

export const metadata = {
  title: "AI Search",
  description: "Search GitHub users and Google Docs with AI",
};

export default function SearchLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="app-shell min-h-screen">
      <Navbar />
      <main className="app-main mx-auto max-w-[1600px] px-4 py-6 sm:px-6">{children}</main>
    </div>
  );
}
