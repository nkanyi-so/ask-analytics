"use client";

import { useState, type FormEvent, type ReactNode } from "react";

import { windowLabel } from "@/lib/format";
import { SUGGESTED_QUESTIONS } from "@/lib/suggested";
import type { AskResponse, ErrorBody } from "@/lib/types";

type Reply = { kind: "answer"; body: AskResponse } | { kind: "error"; message: string };

async function ask(question: string): Promise<Reply> {
  try {
    const response = await fetch("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });
    const body: unknown = await response.json();
    if (!response.ok) {
      return { kind: "error", message: (body as ErrorBody).detail ?? "Something went wrong." };
    }
    return { kind: "answer", body: body as AskResponse };
  } catch {
    return { kind: "error", message: "Could not reach the assistant." };
  }
}

function Answer({ body }: { body: AskResponse }): ReactNode {
  return (
    <div className={body.refused ? "answer refused" : "answer"}>
      {/* Plain text on purpose: the answer is model output and is never rendered as HTML. */}
      <p>{body.answer}</p>
      {body.lookups_called.length > 0 ? (
        <p className="answer-source">
          Looked up:{" "}
          {body.lookups_called.map((call) => `${call.name} (${windowLabel(call.window)})`).join(", ")}
        </p>
      ) : (
        <p className="answer-source">No lookup was used.</p>
      )}
    </div>
  );
}

export function AskBox({ demoMode }: { demoMode: boolean }): ReactNode {
  const [question, setQuestion] = useState("");
  const [reply, setReply] = useState<Reply | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(text: string): Promise<void> {
    const trimmed = text.trim();
    if (!trimmed || busy) return;
    setQuestion(trimmed);
    setBusy(true);
    setReply(await ask(trimmed));
    setBusy(false);
  }

  function onSubmit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    void submit(question);
  }

  return (
    <section className="ask" aria-labelledby="ask-heading">
      <h2 id="ask-heading">Ask</h2>
      {demoMode ? (
        <p className="demo-mode" role="note">
          Demo mode: recorded answers, live model not connected
        </p>
      ) : null}
      <form onSubmit={onSubmit}>
        <label htmlFor="question">Ask about the numbers on this page</label>
        <div className="ask-row">
          <input
            id="question"
            name="question"
            value={question}
            maxLength={500}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder="How many invoices were issued in the last 7 days?"
          />
          <button type="submit" disabled={busy}>
            {busy ? "Asking…" : "Ask"}
          </button>
        </div>
      </form>
      <ul className="suggestions" aria-label="Suggested questions">
        {SUGGESTED_QUESTIONS.map((suggestion) => (
          <li key={suggestion}>
            <button type="button" disabled={busy} onClick={() => void submit(suggestion)}>
              {suggestion}
            </button>
          </li>
        ))}
      </ul>
      {/* Always in the page, so screen readers announce the answer when it arrives. */}
      <div aria-live="polite">
        {reply?.kind === "answer" ? <Answer body={reply.body} /> : null}
        {reply?.kind === "error" ? <p className="answer error">{reply.message}</p> : null}
      </div>
    </section>
  );
}
