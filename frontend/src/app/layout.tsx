import type { Metadata } from "next";
import { Inter, Roboto } from "next/font/google";
import PointerInteractions from "@/components/PointerInteractions";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

const roboto = Roboto({
  weight: ["400", "500", "700"],
  subsets: ["latin"],
  variable: "--font-roboto",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Outreach Console",
  description: "Integrated GitHub scraping and Google Drive indexing",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="en"
      className={`${inter.variable} ${roboto.variable}`}
      suppressHydrationWarning
    >
      <body className="font-sans" suppressHydrationWarning>
        <PointerInteractions />
        {children}
      </body>
    </html>
  );
}
