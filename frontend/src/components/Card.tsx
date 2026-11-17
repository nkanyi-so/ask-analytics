import type { ReactNode } from "react";

/** The one container the dashboard uses: a titled surface with a note under the title. */
export function Card({
  id,
  title,
  note,
  wide = false,
  children,
}: {
  id: string;
  title: string;
  note?: string;
  wide?: boolean;
  children: ReactNode;
}): ReactNode {
  return (
    <section className={wide ? "card wide" : "card"} aria-labelledby={id}>
      <header className="card-head">
        <h2 id={id}>{title}</h2>
        {note ? <p>{note}</p> : null}
      </header>
      {children}
    </section>
  );
}
