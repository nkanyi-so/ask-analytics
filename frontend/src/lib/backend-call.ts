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
        // A header of our own, because proxies in between rewrite X-Forwarded-For.
        "X-Visitor-Address": visitor,
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
 * The visitor's address, for the backend's rate limit.
 *
 * Only a platform that sets `x-real-ip` itself and overwrites the browser's value can
 * be believed, so the header is read only when `onTrustedPlatform` is true (Vercel).
 * Anywhere else a browser could pick its own address per request and dodge the limit,
 * so every visitor shares one key: stricter, never looser.
 */
export function visitorFrom(headers: Headers, onTrustedPlatform: boolean): string {
  const real = onTrustedPlatform ? headers.get("x-real-ip")?.trim() : undefined;
  return real || "shared";
}

const MAX_BODY_BYTES = 4096;

/**
 * Why a request to the Ask route is turned away before its body is read, if it is.
 *
 * The route has no cookie or session, so another site cannot steal anything through
 * it. But it could make its visitors' browsers ask questions, each from a different
 * address, and drain the daily budget. Requiring JSON forces a preflight that fails,
 * and browsers say which site a request comes from.
 */
export function rejection(headers: Headers): Forwarded | null {
  const site = headers.get("sec-fetch-site");
  if (site !== null && site !== "same-origin") {
    return { status: 403, body: { detail: "Ask from the dashboard itself." } };
  }
  if (!(headers.get("content-type") ?? "").toLowerCase().startsWith("application/json")) {
    return { status: 415, body: { detail: "Send the question as JSON." } };
  }
  if (Number(headers.get("content-length") ?? "0") > MAX_BODY_BYTES) {
    return { status: 413, body: { detail: "Ask a question of up to 500 characters." } };
  }
  return null;
}
