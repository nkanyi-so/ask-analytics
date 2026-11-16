import type { Metadata, Viewport } from "next";
import { Hanken_Grotesk } from "next/font/google";
import type { ReactNode } from "react";
import "./globals.css";

// One family for everything. Self-hosted at build time: no request leaves the page.
const sans = Hanken_Grotesk({ subsets: ["latin"], variable: "--font-sans", display: "swap" });

export const metadata: Metadata = {
  title: "ask-analytics",
  description:
    "Usage numbers for a seeded workspace, and an assistant that can only answer with numbers the page can derive.",
};

export const viewport: Viewport = { colorScheme: "light dark" };

export default function RootLayout({ children }: { children: ReactNode }): ReactNode {
  return (
    <html lang="en" className={sans.variable}>
      <body>
        <div className="page">{children}</div>
      </body>
    </html>
  );
}
