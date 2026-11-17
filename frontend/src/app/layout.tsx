import type { Metadata, Viewport } from "next";
import { Hanken_Grotesk } from "next/font/google";
import { Suspense, type ReactNode } from "react";

import { Shell } from "@/components/Shell";
import { getHealth } from "@/lib/backend";

import "./globals.css";

// One family for everything. Self-hosted at build time: no request leaves the page.
const sans = Hanken_Grotesk({ subsets: ["latin"], variable: "--font-sans", display: "swap" });

export const metadata: Metadata = {
  title: "ask-analytics",
  description:
    "Usage numbers for a seeded workspace, and an assistant that can only answer with numbers the page can derive.",
};

export const viewport: Viewport = { colorScheme: "light dark" };

// The frame asks the backend one thing: is this demo mode? Read per request, never at build.
export const dynamic = "force-dynamic";

async function demoMode(): Promise<boolean | null> {
  try {
    return (await getHealth()).demo_mode;
  } catch {
    // The view below will say the backend is unreachable; the frame makes no claim.
    return null;
  }
}

export default async function RootLayout({ children }: { children: ReactNode }): Promise<ReactNode> {
  return (
    <html lang="en" className={sans.variable}>
      <body>
        {/* The frame reads the address bar, which needs a boundary on the server. */}
        <Suspense>
          <Shell demoMode={await demoMode()}>{children}</Shell>
        </Suspense>
      </body>
    </html>
  );
}
