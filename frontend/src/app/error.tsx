"use client";

import type { ReactNode } from "react";

export default function PageError({ reset }: { error: Error; reset: () => void }): ReactNode {
  return (
    <main>
      <h1>The numbers could not be loaded</h1>
      <p>The dashboard could not reach its backend. Check that it is running, then try again.</p>
      <button type="button" onClick={reset}>
        Try again
      </button>
    </main>
  );
}
