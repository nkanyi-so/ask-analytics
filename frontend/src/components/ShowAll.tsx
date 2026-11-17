"use client";

import { useState, type ReactNode } from "react";

/**
 * A long table, shown short until asked for in full. Every row is rendered either way;
 * this only decides how many are visible, so nothing is counted or fetched here.
 */
export function ShowAll({ more, fewer, children }: { more: string; fewer: string; children: ReactNode }): ReactNode {
  const [all, setAll] = useState(false);
  return (
    <div className="show-all" data-all={all}>
      {children}
      <button className="text-button" type="button" aria-expanded={all} onClick={() => setAll(!all)}>
        {all ? fewer : more}
      </button>
    </div>
  );
}
