"use client";

import type { ReactNode } from "react";

import { useAsk } from "./ask-context";

/**
 * Makes a tile a way into the assistant: press it and the question is asked for you.
 * The tile shows "Ask about this" in place of its caption while it is pointed at.
 * Left out in demo mode, where a question written on the spot has no recorded answer.
 */
export function AskAbout({ label, question }: { label: string; question: string }): ReactNode {
  const { ask, live } = useAsk();
  if (!live) return null;
  return (
    <button className="tile-ask" type="button" onClick={() => ask(question)}>
      <span className="visually-hidden">{label}</span>
    </button>
  );
}
