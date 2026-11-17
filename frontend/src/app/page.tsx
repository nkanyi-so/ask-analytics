import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";

import { Dashboard } from "@/components/Dashboard";
import { getOverview } from "@/lib/backend";
import { formatDay } from "@/lib/format";
import { parseWindow } from "@/lib/windows";

export const metadata: Metadata = { title: "Overview" };

type SearchParams = Promise<Record<string, string | string[] | undefined>>;

export default async function OverviewPage({
  searchParams,
}: {
  searchParams: SearchParams;
}): Promise<ReactNode> {
  const window = parseWindow((await searchParams).window);
  const overview = await getOverview(window);

  return (
    <main className="view">
      <h1 className="visually-hidden">Usage overview</h1>
      <p className="demo-note">
        <span className="pill brand">Demo</span>
        <span>
          Made-up data, running to <time dateTime={overview.as_of}>{formatDay(overview.as_of)}</time>, and an{" "}
          <strong>AI assistant that cannot invent a number</strong>.
        </span>
        <Link href="/about">How it works</Link>
      </p>
      {/* Not keyed by window: the chosen number and the table's sort survive a change of window. */}
      <Dashboard overview={overview} />
    </main>
  );
}
