"use client";

import { useRef, useState, type FormEvent, type ReactNode } from "react";

import { heroOf, numbersOf, segmentsOf, type Segment } from "@/lib/answer";
import { figuresIn, isLookup, LOOKUP_NAMES, shownFor, type EvidenceRow, type Shown } from "@/lib/evidence";
import { beforeLabel, formatChange, formatCount, windowLabel } from "@/lib/format";
import { SUGGESTED_QUESTIONS } from "@/lib/suggested";
import type { AskResponse, ErrorBody, LookupCalled } from "@/lib/types";

const MAX_LENGTH = 500;

type State =
  | { kind: "idle" }
  | { kind: "loading"; question: string }
  | { kind: "answer"; question: string; body: AskResponse; evidence: (EvidenceRow[] | null)[] }
  | { kind: "limit"; question: string; message: string; budget: boolean }
  | { kind: "failed"; question: string; message: string; retry: boolean };

const EVIDENCE_WAIT_MS = 4000;

/** Re-read what one lookup returned. `null` if it cannot be had quickly: the answer stands without it. */
async function evidenceFor(call: LookupCalled): Promise<EvidenceRow[] | null> {
  if (!isLookup(call.name)) return null;
  const query = new URLSearchParams({ lookup: call.name, window: call.window });
  if (call.args.with_previous === true) query.set("previous", "1");
  if (typeof call.args.user_id === "string") query.set("user_id", call.args.user_id);
  if (typeof call.args.tool_id === "string") query.set("tool_id", call.args.tool_id);
  try {
    // An answer that has arrived is never held up for long by its own footnotes.
    const response = await fetch(`/api/evidence?${query.toString()}`, {
      signal: AbortSignal.timeout(EVIDENCE_WAIT_MS),
    });
    return response.ok ? ((await response.json()) as { rows: EvidenceRow[] }).rows : null;
  } catch {
    return null;
  }
}

async function ask(question: string): Promise<State> {
  let response: Response;
  let body: unknown;
  try {
    response = await fetch("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });
    body = await response.json();
  } catch {
    return { kind: "failed", question, message: "The assistant could not be reached.", retry: true };
  }
  if (response.ok) {
    const answer = body as AskResponse;
    const evidence = answer.refused ? [] : await Promise.all(answer.lookups_called.map(evidenceFor));
    return { kind: "answer", question, body: answer, evidence };
  }
  const message = (body as ErrorBody).detail ?? "Something went wrong.";
  if (response.status === 429) {
    // Both limits arrive as a 429; only the backend's wording tells them apart.
    return { kind: "limit", question, message, budget: message.toLowerCase().includes("budget") };
  }
  return { kind: "failed", question, message, retry: response.status >= 500 };
}

function Tick(): ReactNode {
  return (
    <svg viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <path d="M2.5 8.5l3.5 3.5 7.5-8" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

/** The answer's own words, with the numbers the page found in the result marked. */
function Marked({ segments, figures }: { segments: Segment[]; figures: Set<number> }): ReactNode {
  return segments.map((segment, index) =>
    segment.value !== undefined && figures.has(segment.value) ? (
      <mark key={index} className="checked">
        {segment.text}
        <span className="visually-hidden"> (in the result)</span>
      </mark>
    ) : (
      segment.text
    ),
  );
}

function Row({ row, against }: { row: EvidenceRow; against: string }): ReactNode {
  return (
    <li>
      <div className="row-title">{row.title}</div>
      <dl className="facts">
        {row.facts.map((fact) => (
          <div key={fact.label}>
            <dt>{fact.label}</dt>
            <dd>{formatCount(fact.value)}</dd>
            {fact.previous !== undefined ? (
              <>
                <dt>, {against}</dt>
                <dd>{fact.previous === null ? "no earlier data" : formatCount(fact.previous)}</dd>
              </>
            ) : null}
            {fact.change !== undefined && fact.change !== null ? (
              <>
                <dt>, change</dt>
                <dd>{formatChange(fact.change)}</dd>
              </>
            ) : null}
          </div>
        ))}
      </dl>
      {row.names && row.names.length > 0 ? <div>{row.names.join(", ")}</div> : null}
    </li>
  );
}

function LookupSteps({ call, shown }: { call: LookupCalled; shown: Shown | null }): ReactNode {
  const compared = call.args.with_previous === true;
  const name = isLookup(call.name) ? LOOKUP_NAMES[call.name] : call.name;
  return (
    <>
      <li>
        <div>
          <div className="step-title">Looked up {name}</div>
          <div className="step-detail">
            For {windowLabel(call.window)}
            {compared ? `, and ${beforeLabel(call.window)}` : ""}.
          </div>
        </div>
      </li>
      <li>
        <div>
          <div className="step-title">Got back</div>
          {shown === null ? (
            <div className="step-detail">The result could not be re-read just now. It is in the tables below.</div>
          ) : shown.rows.length === 0 ? (
            <div className="step-detail">The full result is in the tables below.</div>
          ) : (
            <>
              <ul className="rows">
                {shown.rows.map((row) => (
                  <Row key={row.title} row={row} against={beforeLabel(call.window)} />
                ))}
              </ul>
              {shown.more ? <div className="step-detail">More rows matched. They are in the tables below.</div> : null}
            </>
          )}
        </div>
      </li>
    </>
  );
}

function Answered({ body, evidence }: { body: AskResponse; evidence: (EvidenceRow[] | null)[] }): ReactNode {
  // The model sometimes writes Markdown bold. This page renders plain text only.
  const text = body.answer.replaceAll("**", "");
  const segments = segmentsOf(text);
  const numbers = numbersOf(segments);
  const hero = heroOf(segments);
  const shown = body.lookups_called.map((_, index) => {
    const rows = evidence[index] ?? null;
    return rows === null ? null : shownFor(rows, text, numbers);
  });
  const figures = figuresIn(shown.filter((each) => each !== null));
  const anyMarked = [...numbers].some((value) => figures.has(value));

  return (
    <div className="panel-body answered arrive">
      <div>
        {hero === null ? (
          <p className="hero-words">
            <Marked segments={segments} figures={figures} />
          </p>
        ) : (
          <>
            <p className="hero-number" aria-hidden="true">
              {hero}
            </p>
            <p className="answer-text">
              <Marked segments={segments} figures={figures} />
            </p>
          </>
        )}
      </div>
      <div className="working">
        <h2>How this was worked out</h2>
        <ol className="steps">
          {body.lookups_called.map((call, index) => (
            <LookupSteps key={index} call={call} shown={shown[index]} />
          ))}
          <li>
            <div>
              <div className="step-title">
                <Tick />
                Checked
              </div>
              <div className="step-detail">
                Before an answer is sent, every number in it must be in a lookup result. An answer with any
                other number is replaced by a refusal.
                {anyMarked ? " Numbers marked in the answer are in the rows shown here." : ""}
              </div>
            </div>
          </li>
        </ol>
        <p className="cost">
          {body.demo_mode
            ? "Recorded answer. No model was called."
            : `Answered in ${formatCount(body.latency_ms)} ms for $${body.cost_usd.toFixed(4)}.`}
        </p>
      </div>
    </div>
  );
}

function Refused({ body }: { body: AskResponse }): ReactNode {
  // In demo mode the backend says so in its own words when a question has no recording.
  const unrecorded = body.demo_mode && body.answer.startsWith("Demo mode");
  return (
    <div className="notice arrive">
      <p className="hero-words">
        {unrecorded ? "There is no recorded answer for that question." : "That can't be answered from this data."}
      </p>
      <p>{body.answer}</p>
      {unrecorded ? null : (
        <p>
          {body.lookups_called.length === 0
            ? "No lookup ran. The assistant refuses rather than guesses."
            : "A lookup ran, but it did not lead to an answer that could be shown."}
        </p>
      )}
    </div>
  );
}

export function AskPanel({ demoMode }: { demoMode: boolean }): ReactNode {
  const [question, setQuestion] = useState("");
  const [state, setState] = useState<State>({ kind: "idle" });
  const field = useRef<HTMLInputElement>(null);
  const busy = state.kind === "loading";

  async function submit(text: string): Promise<void> {
    const trimmed = text.trim();
    if (busy) return;
    if (!trimmed) {
      // Nothing to ask yet: put the reader in the field instead of greying the button out.
      field.current?.focus();
      return;
    }
    setQuestion(trimmed);
    setState({ kind: "loading", question: trimmed });
    setState(await ask(trimmed));
  }

  function onSubmit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    void submit(question);
  }

  return (
    <section className="ask" aria-label="Ask a question">
      <form onSubmit={onSubmit}>
        <label className="ask-label" htmlFor="question">
          Ask about usage, people, clients or errors
        </label>
        <div className="ask-row">
          <input
            id="question"
            ref={field}
            name="question"
            value={question}
            maxLength={MAX_LENGTH}
            // Read-only, not disabled, while waiting: a disabled field drops keyboard focus.
            readOnly={busy}
            autoComplete="off"
            aria-describedby="ask-hint"
            onChange={(event) => setQuestion(event.target.value)}
            placeholder="How many invoices were issued in the last 7 days?"
          />
          <button className="button" type="submit" aria-disabled={busy}>
            {busy ? "Asking" : "Ask"}
          </button>
        </div>
        <p className="ask-hint" id="ask-hint">
          {question.length >= MAX_LENGTH
            ? `A question can be ${MAX_LENGTH} characters at most.`
            : demoMode
              ? "Demo mode: recorded answers, live model not connected."
              : "Covers today, the last 7 days or the last 30 days."}
        </p>
      </form>
      <ul className="suggestions" aria-label="Questions to try">
        {SUGGESTED_QUESTIONS.map((suggestion) => (
          <li key={suggestion}>
            <button type="button" aria-disabled={busy} onClick={() => void submit(suggestion)}>
              {suggestion}
            </button>
          </li>
        ))}
      </ul>

      {/* Always in the page, so a screen reader announces whatever arrives. */}
      <div className="answer-region" aria-live="polite">
        {state.kind === "idle" ? null : (
          <div className="panel">
            <p className="panel-question">You asked: {state.question}</p>
            {state.kind === "loading" ? (
              <div className="panel-body">
                <p className="answer-text">Looking it up. This usually takes a few seconds.</p>
              </div>
            ) : null}
            {state.kind === "answer" ? (
              state.body.refused ? (
                <div className="panel-body">
                  <Refused body={state.body} />
                </div>
              ) : (
                <Answered body={state.body} evidence={state.evidence} />
              )
            ) : null}
            {state.kind === "limit" ? (
              <div className="panel-body">
                <div className="notice">
                  <p className="hero-words">
                    {state.budget ? "The assistant has stopped for today." : "Too many questions for now."}
                  </p>
                  <p>{state.message}</p>
                  <p>
                    {state.budget
                      ? "The dashboard below still works."
                      : "Your question is still in the field."}
                  </p>
                </div>
              </div>
            ) : null}
            {state.kind === "failed" ? (
              <div className="panel-body">
                <div className="notice">
                  <p className="hero-words">
                    {state.retry ? "The assistant could not be reached." : "That question could not be sent."}
                  </p>
                  <p>{state.message}</p>
                  {state.retry ? (
                    <button
                      className="button quiet"
                      type="button"
                      onClick={() => {
                        // This button is about to leave the page; hand focus to the field first.
                        field.current?.focus();
                        void submit(state.question);
                      }}
                    >
                      Try again
                    </button>
                  ) : null}
                </div>
              </div>
            ) : null}
          </div>
        )}
      </div>
    </section>
  );
}
