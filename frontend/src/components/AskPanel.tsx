"use client";

import { useEffect, useImperativeHandle, useRef, useState, type FormEvent, type ReactNode, type Ref } from "react";

import { heroOf, numbersOf, segmentsOf, type Segment } from "@/lib/answer";
import { figuresIn, isLookup, LOOKUP_NAMES, shownFor, type EvidenceRow, type Shown } from "@/lib/evidence";
import { beforeLabel, formatChange, formatCount, windowLabel } from "@/lib/format";
import { REFUSED_QUESTION, SUGGESTED_QUESTIONS } from "@/lib/suggested";
import type { AskResponse, ErrorBody, LookupCalled } from "@/lib/types";

const MAX_LENGTH = 500;

/** What came back for one question. */
type Outcome =
  | { kind: "loading" }
  | { kind: "answer"; body: AskResponse; evidence: (EvidenceRow[] | null)[] }
  | { kind: "limit"; message: string; budget: boolean }
  | { kind: "failed"; message: string; retry: boolean };

/** One question and what came back. Each stands alone: the assistant keeps no memory of the last. */
interface Entry {
  id: number;
  question: string;
  outcome: Outcome;
}

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

async function ask(question: string): Promise<Outcome> {
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
    return { kind: "failed", message: "The assistant could not be reached.", retry: true };
  }
  if (response.ok) {
    const answer = body as AskResponse;
    const evidence = answer.refused ? [] : await Promise.all(answer.lookups_called.map(evidenceFor));
    return { kind: "answer", body: answer, evidence };
  }
  const message = (body as ErrorBody).detail ?? "Something went wrong.";
  if (response.status === 429) {
    // Both limits arrive as a 429; only the backend's wording tells them apart.
    return { kind: "limit", message, budget: message.toLowerCase().includes("budget") };
  }
  return { kind: "failed", message, retry: response.status >= 500 };
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
            <div className="step-detail">The result could not be re-read just now. It is on the dashboard.</div>
          ) : shown.rows.length === 0 ? (
            <div className="step-detail">The full result is on the dashboard.</div>
          ) : (
            <>
              <ul className="rows">
                {shown.rows.map((row) => (
                  <Row key={row.title} row={row} against={beforeLabel(call.window)} />
                ))}
              </ul>
              {shown.more ? <div className="step-detail">More rows matched. They are on the dashboard.</div> : null}
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
    <div className="answer arrive">
      <div className="answer-top">
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
      {/* The answer is announced; the steps are there to be read, not read out. */}
      <div className="working" aria-live="off">
        <h3>How this was worked out</h3>
        <ol className="steps">
          {body.lookups_called.map((call, index) => (
            <LookupSteps key={index} call={call} shown={shown[index]} />
          ))}
          <li className="ok">
            <div>
              <div className="step-title">Checked</div>
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
    <div className="answer notice arrive">
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

function EntryView({ entry, onRetry }: { entry: Entry; onRetry: () => void }): ReactNode {
  const { outcome } = entry;
  return (
    <li className="entry">
      <p className="question">
        <span className="visually-hidden">You asked: </span>
        {entry.question}
      </p>
      {outcome.kind === "loading" ? (
        <div className="answer waiting">
          <p>Looking it up. This usually takes a few seconds.</p>
        </div>
      ) : null}
      {outcome.kind === "answer" ? (
        outcome.body.refused ? (
          <Refused body={outcome.body} />
        ) : (
          <Answered body={outcome.body} evidence={outcome.evidence} />
        )
      ) : null}
      {outcome.kind === "limit" ? (
        <div className="answer notice">
          <p className="hero-words">
            {outcome.budget ? "The assistant has stopped for today." : "Too many questions for now."}
          </p>
          <p>{outcome.message}</p>
          <p>{outcome.budget ? "The dashboard still works." : "Ask it again in a minute."}</p>
        </div>
      ) : null}
      {outcome.kind === "failed" ? (
        <div className="answer notice">
          <p className="hero-words">
            {outcome.retry ? "The assistant could not be reached." : "That question could not be sent."}
          </p>
          <p>{outcome.message}</p>
          {outcome.retry ? (
            <button className="button quiet" type="button" onClick={onRetry}>
              Try again
            </button>
          ) : null}
        </div>
      ) : null}
    </li>
  );
}

/** What the frame can tell the assistant to do. */
export interface AskHandle {
  /** Ask this as if it had been typed. If a question is still being answered, it waits in the field. */
  ask: (question: string) => void;
}

interface AskPanelProps {
  /** `null` when the backend could not say: the panel then makes no claim either way. */
  demoMode: boolean | null;
  /** Rises each time the panel is opened by hand, to put the cursor in the field. */
  opened: number;
  /** True when the panel lies over the page: it is then a dialog, and the page is inert. */
  modal: boolean;
  handle: Ref<AskHandle>;
  onClose: () => void;
}

/**
 * The assistant, mounted once in the layout so its answers survive a change of view.
 * It is a running list of separate questions, not a conversation: the backend answers
 * each question with no memory of the one before.
 */
export function AskPanel({ demoMode, opened, modal, handle, onClose }: AskPanelProps): ReactNode {
  const [question, setQuestion] = useState("");
  const [entries, setEntries] = useState<Entry[]>([]);
  const field = useRef<HTMLInputElement>(null);
  const transcript = useRef<HTMLDivElement>(null);
  const nextId = useRef(1);
  const busy = entries.some((entry) => entry.outcome.kind === "loading");
  const latest = entries.at(-1);

  useEffect(() => {
    if (opened > 0) field.current?.focus();
  }, [opened]);

  // Bring the newest question to the top of the list, so its answer has room to arrive.
  useEffect(() => {
    const box = transcript.current;
    const last = box?.querySelector<HTMLElement>(".entry:last-child");
    if (box && last) box.scrollTo({ top: last.offsetTop - box.offsetTop });
  }, [latest?.id, latest?.outcome.kind]);

  async function submit(text: string): Promise<void> {
    const trimmed = text.trim();
    if (busy) return;
    if (!trimmed) {
      // Nothing to ask yet: put the reader in the field instead of greying the button out.
      field.current?.focus();
      return;
    }
    const id = nextId.current;
    nextId.current += 1;
    setQuestion("");
    setEntries((before) => [...before, { id, question: trimmed, outcome: { kind: "loading" } }]);
    await run(id, trimmed);
  }

  async function run(id: number, text: string): Promise<void> {
    const outcome = await ask(text);
    setEntries((before) => before.map((entry) => (entry.id === id ? { ...entry, outcome } : entry)));
  }

  /** Ask a failed question again in place, so no stale failure is left in the list. */
  function retry(entry: Entry): void {
    if (busy) return;
    // The button is about to leave the page; hand focus to the field first.
    field.current?.focus();
    setEntries((before) => before.map((each) => (each.id === entry.id ? { ...each, outcome: { kind: "loading" } } : each)));
    void run(entry.id, entry.question);
  }

  // A question handed over from the dashboard is asked as if it had been typed. One at
  // a time: if another is still being answered, this one is kept in the field.
  useImperativeHandle(handle, () => ({
    ask: (text: string) => {
      if (busy) setQuestion(text);
      else void submit(text);
    },
  }));

  function onSubmit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    void submit(question);
  }

  return (
    <aside
      className="ask"
      aria-labelledby="ask-title"
      role={modal ? "dialog" : undefined}
      aria-modal={modal ? true : undefined}
    >
      <div className="ask-head">
        <div>
          <h2 id="ask-title">
            Ask{" "}
            {demoMode === null ? null : <span className={demoMode ? "pill" : "pill good"}>{demoMode ? "Demo" : "Live"}</span>}
          </h2>
          <p className="ask-mode">
            {demoMode === true
              ? "Demo mode: recorded answers, live model not connected."
              : "It can look a number up. It cannot make one up."}
          </p>
        </div>
        <button className="round-button" type="button" onClick={onClose} aria-label="Close the Ask panel">
          <svg viewBox="0 0 16 16" fill="none" aria-hidden="true">
            <path d="M3.5 3.5l9 9m0-9l-9 9" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
          </svg>
        </button>
      </div>

      {/* A log, so a screen reader announces each answer as it arrives. */}
      <div className="transcript" ref={transcript} role="log" aria-live="polite" tabIndex={entries.length > 0 ? 0 : -1} aria-label="Questions and answers">
        {entries.length === 0 ? (
          <div className="ask-empty">
            <p className="ask-pitch">An assistant that cannot make a number up.</p>
            <p>
              Ask in plain English. It can only look a number up, never work one out, and every
              answer shows which lookup ran and that the number was checked.
            </p>
            <h3>Questions to try</h3>
            <ul className="suggestions">
              {SUGGESTED_QUESTIONS.map((suggestion) => (
                <li key={suggestion}>
                  <button type="button" onClick={() => void submit(suggestion)}>
                    {suggestion}
                  </button>
                </li>
              ))}
            </ul>
            <h3>One it should refuse</h3>
            <ul className="suggestions">
              <li>
                <button type="button" onClick={() => void submit(REFUSED_QUESTION)}>
                  {REFUSED_QUESTION}
                </button>
              </li>
            </ul>
          </div>
        ) : (
          <ol className="entries">
            {entries.map((entry) => (
              <EntryView key={entry.id} entry={entry} onRetry={() => retry(entry)} />
            ))}
          </ol>
        )}
      </div>

      <form className="composer" onSubmit={onSubmit}>
        <label className="visually-hidden" htmlFor="question">
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
            placeholder="Ask a question"
          />
          <button className="button" type="submit" aria-disabled={busy}>
            {busy ? "Asking" : "Ask"}
          </button>
        </div>
        <p className="ask-hint" id="ask-hint">
          {question.length >= MAX_LENGTH
            ? `A question can be ${MAX_LENGTH} characters at most.`
            : "Each question stands alone. Covers today, the last 7 days or the last 30 days."}
        </p>
      </form>
    </aside>
  );
}
