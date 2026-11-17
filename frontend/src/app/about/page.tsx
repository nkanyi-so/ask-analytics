import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";

import { EVAL_RUNS, REPO_URL } from "@/lib/about";

export const metadata: Metadata = { title: "About" };

export default function AboutPage(): ReactNode {
  return (
    <main className="view">
      <h1 className="visually-hidden">About this demo</h1>
      <p className="lede">
        A rebuild, on made-up data, of usage reporting I built for a client&apos;s internal platform. The
        tools, the people and every number here are invented. The method is the real one.
      </p>

      <section className="card prose-card" aria-labelledby="problem">
        <h2 id="problem">The question it answers</h2>
        <p>
          A company gives its people a set of internal tools. Months later someone asks: who is actually
          using what? The answer usually lives in an analytics product that only engineers open, where
          every tool counts success differently and anyone who never logged in does not appear at all.
        </p>
        <p>
          The <Link href="/">Overview</Link> gives the numbers that answer it, each one a button that opens
          the chart and the tables behind it, including the people who were invited and never showed up.{" "}
          <Link href="/reliability">Reliability</Link> shows what is failing and who it reached.
        </p>
      </section>

      <section className="card prose-card" aria-labelledby="honest">
        <h2 id="honest">Why the assistant cannot make a number up</h2>
        <p>
          Language models are fluent and will state a figure with confidence whether or not it is true. So
          this one is never asked for a figure. It is asked to choose.
        </p>
        <ol className="how">
          <li>
            <strong>It never sees the raw data.</strong> It is given five lookups it may call, such as
            &ldquo;usage by tool&rdquo;, and three time ranges.
          </li>
          <li>
            <strong>The code does every sum.</strong> The lookup counts, and works out the change from the
            period before. The model never adds or subtracts.
          </li>
          <li>
            <strong>Every number in the answer is checked.</strong> If the answer contains a number that
            was not in a lookup result, it is thrown away and replaced with a refusal.
          </li>
          <li>
            <strong>No lookup, no answer.</strong> A question the data cannot answer, such as a forecast, is
            refused, with a list of what can be asked.
          </li>
        </ol>
        <p>Each answer in the Ask panel shows this working: the lookup, what came back, and the check.</p>
      </section>

      <section className="card prose-card" aria-labelledby="tested">
        <h2 id="tested">How it is tested</h2>
        <p>
          Forty questions with answers that are known in advance, because the data is generated and the
          right answers are computed alongside it. Ten of the forty must be refused. Each question is
          asked three times against the real model and only counts if it is right all three times. There
          is no second model marking the first.
        </p>
        <table className="data" role="table">
          <thead role="rowgroup">
            <tr role="row">
              <th role="columnheader" scope="col">
                Run
              </th>
              <th role="columnheader" scope="col" className="num">
                Direct
              </th>
              <th role="columnheader" scope="col" className="num">
                Indirect
              </th>
              <th role="columnheader" scope="col" className="num">
                Comparison
              </th>
              <th role="columnheader" scope="col" className="num">
                Must refuse
              </th>
            </tr>
          </thead>
          <tbody role="rowgroup">
            {EVAL_RUNS.map((run) => (
              <tr role="row" key={run.label}>
                <th role="rowheader" scope="row">
                  {run.label}
                </th>
                <td role="cell" className="num" data-label="Direct">
                  {run.direct}
                </td>
                <td role="cell" className="num" data-label="Indirect">
                  {run.indirect}
                </td>
                <td role="cell" className="num" data-label="Comparison">
                  {run.comparison}
                </td>
                <td role="cell" className="num" data-label="Must refuse">
                  {run.refusal}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <p>
          The early runs found real faults: the model was never told which tools exist, so it refused fair
          questions, and it wrote &ldquo;Three people&rdquo; where the check expected a 3. Each fault and
          its fix is written up in the repository. The later score is partly fitted to these forty
          questions, since they are what the fixes were tested on.
        </p>
      </section>

      <section className="card prose-card" aria-labelledby="real">
        <h2 id="real">What is real and what is not</h2>
        <ul className="how">
          <li>
            <strong>Made up:</strong> eight tools, forty people, six clients and sixty days of activity,
            generated from a fixed seed. &ldquo;Today&rdquo; is pinned to the last day of that data.
          </li>
          <li>
            <strong>Real:</strong> the lookups, the checks, the tests, and the model. When the page is
            marked &ldquo;demo mode&rdquo;, answers are recorded ones and no model is called.
          </li>
        </ul>
        <p>
          <a href={REPO_URL}>Source code, tests and the full write-up</a>
        </p>
      </section>
    </main>
  );
}
