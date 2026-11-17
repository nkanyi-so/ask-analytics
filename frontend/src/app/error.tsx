"use client";

import type { ReactNode } from "react";

export default function PageError({ reset }: { error: Error; reset: () => void }): ReactNode {
  return (
    <main className="view">
      <div className="card notice pad">
        <h1 className="hero-words">The numbers could not be loaded.</h1>
        <p>The page could not reach the service that holds the data. Nothing is lost; it only needs to answer.</p>
        <button className="button quiet" type="button" onClick={reset}>
          Try again
        </button>
      </div>
    </main>
  );
}
