import "./drive.css";
import { DocsBrowseProvider } from "@/lib/docs-browse-context";
import ModuleSubnav from "@/components/ModuleSubnav";
import Navbar from "@/components/Navbar";

export default function ExploreDriveLayout({ children }: { children: React.ReactNode }) {
  return (
    <DocsBrowseProvider>
      <div className="app-shell app-shell--docs app-shell--drive min-h-screen">
        <Navbar />
        <ModuleSubnav />
        <main className="app-main app-main--docs mx-auto max-w-[1600px] px-4 py-6 sm:px-6">{children}</main>
      </div>
    </DocsBrowseProvider>
  );
}
