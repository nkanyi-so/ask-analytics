// How the frontend's server talks to the backend. No environment access here, so it
// can be tested; `backend.ts` supplies the URL and the token and is server-only.
import type { AskResponse, ErrorBody } from "./types";

export interface BackendConfig {
  url: string;
  token: string;
}

export interface Forwarded {
  status: number;
  body: AskResponse | ErrorBody;
}

const MAX_QUESTION_LENGTH = 500;

export async function backendGet<T>(
  config: BackendConfig,
  path: string,
  fetchImpl: typeof fetch = fetch,
): Promise<T> {
  const response = await fetchImpl(`${config.url}${path}`, {
    headers: { Authorization: `Bearer ${config.token}` },
    // The backend owns the ten-minute cache; the frontend keeps none.
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`Backend replied ${response.status} for ${path}`);
  }
  return (await response.json()) as T;
}

function questionFrom(body: unknown): string | null {
  if (typeof body !== "object" || body === null) return null;
  const question: unknown = (body as Record<string, unknown>).question;
  if (typeof question !== "string") return null;
  return question.length >= 1 && question.length <= MAX_QUESTION_LENGTH ? question : null;
}

/** Send one question to the backend. Returns only a status and a JSON body: no headers. */
export async function forwardAsk(
  config: BackendConfig,
  body: unknown,
  visitor: string,
  fetchImpl: typeof fetch = fetch,
): Promise<Forwarded> {
  const question = questionFrom(body);
  if (question === null) {
    return { status: 400, body: { detail: "Ask a question of up to 500 characters." } };
  }
  try {
    const response = await fetchImpl(`${config.url}/api/ask`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${config.token}`,
        "Content-Type": "application/json",
        // Set here, never copied from the browser: the backend rate-limits on it.
        "X-Forwarded-For": visitor,
      },
      body: JSON.stringify({ question }),
      cache: "no-store",
    });
    return { status: response.status, body: (await response.json()) as AskResponse | ErrorBody };
  } catch {
    return { status: 502, body: { detail: "The backend is not reachable." } };
  }
}

/**
 * The visitor's address as the hosting platform reports it. Vercel sets both headers
 * itself and overwrites what the browser sent. On a host that only appends to
 * X-Forwarded-For, the first entry is the browser's claim and this needs revisiting.
 */
export function visitorFrom(headers: Headers): string {
  const real = headers.get("x-real-ip")?.trim();
  if (real) return real;
  const forwarded = headers.get("x-forwarded-for")?.split(",")[0]?.trim();
  return forwarded || "local";
}
