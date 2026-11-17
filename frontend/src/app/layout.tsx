import type { Metadata, Viewport } from "next";
import { Suspense, type ReactNode } from "react";

import { Shell } from "@/components/Shell";
import { getHealth } from "@/lib/backend";

import "./globals.css";

// A stored choice of theme is applied before the first paint, so the page never flashes
// the other one. With no stored choice, the page follows the system setting (see tokens.css).
const APPLY_THEME = `try{var t=localStorage.getItem("theme");if(t==="light"||t==="dark")document.documentElement.dataset.theme=t}catch(e){}`;

export const metadata: Metadata = {
  title: { default: "ask-analytics", template: "%s · ask-analytics" },
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
    // The script below may set data-theme before React wakes up; that difference is expected.
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: APPLY_THEME }} />
      </head>
      <body>
        {/* The frame reads the address bar, which needs a boundary on the server. */}
        <Suspense>
          <Shell demoMode={await demoMode()}>{children}</Shell>
        </Suspense>
      </body>
    </html>
  );
}
