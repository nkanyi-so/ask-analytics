"use client";

import { createContext, useContext } from "react";

/** How a part of the dashboard hands a question to the assistant. */
export interface AskBridge {
  /** Open the assistant and ask this. */
  ask: (question: string) => void;
  /** False in demo mode, where only recorded questions have answers. */
  live: boolean;
}

export const AskContext = createContext<AskBridge>({ ask: () => {}, live: false });

export function useAsk(): AskBridge {
  return useContext(AskContext);
}
