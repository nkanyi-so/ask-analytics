import { describe, expect, it } from "vitest";

import {
  backendGet,
  forwardAsk,
  rejection,
  visitorFrom,
  type BackendConfig,
} from "./backend-call";

const CONFIG: BackendConfig = { url: "http://backend.test", token: "test-token-not-a-secret" };

interface Call {
  url: string;
  init: RequestInit;
}

function fakeFetch(status: number, body: unknown, calls: Call[]): typeof fetch {
  return async (input, init) => {
    calls.push({ url: String(input), init: init ?? {} });
    return new Response(JSON.stringify(body), { status });
  };
}

function header(call: Call, name: string): string | null {
  return new Headers(call.init.headers).get(name);
}

describe("backendGet", () => {
  it("sends the admin token and never caches", async () => {
    const calls: Call[] = [];
    const body = await backendGet<{ ok: boolean }>(
      CONFIG,
      "/api/overview?window=7d",
      fakeFetch(200, { ok: true }, calls),
    );

    expect(body).toEqual({ ok: true });
    expect(calls[0].url).toBe("http://backend.test/api/overview?window=7d");
    expect(header(calls[0], "authorization")).toBe("Bearer test-token-not-a-secret");
    expect(calls[0].init.cache).toBe("no-store");
  });

  it("throws on a failed reply without echoing the token", async () => {
    const failing = backendGet(CONFIG, "/api/overview?window=7d", fakeFetch(401, {}, []));

    await expect(failing).rejects.toThrow("Backend replied 401");
    await expect(failing).rejects.not.toThrow(CONFIG.token);
  });
});

describe("forwardAsk", () => {
  it("forwards the question with the token and the visitor, and returns only the body", async () => {
    const calls: Call[] = [];
    const reply = { answer: "10 invoices.", refused: false };

    const result = await forwardAsk(
      CONFIG,
      { question: "How many invoices?" },
      "203.0.113.7",
      fakeFetch(200, reply, calls),
    );

    expect(result).toEqual({ status: 200, body: reply });
    expect(calls[0].url).toBe("http://backend.test/api/ask");
    expect(calls[0].init.method).toBe("POST");
    expect(header(calls[0], "authorization")).toBe("Bearer test-token-not-a-secret");
    expect(header(calls[0], "x-visitor-address")).toBe("203.0.113.7");
    expect(header(calls[0], "x-forwarded-for")).toBeNull();
    expect(JSON.parse(String(calls[0].init.body))).toEqual({ question: "How many invoices?" });
    expect(JSON.stringify(result)).not.toContain(CONFIG.token);
  });

  it("passes the backend's limit messages through", async () => {
    const detail = { detail: "Too many questions. Wait a minute and try again." };

    const result = await forwardAsk(CONFIG, { question: "q" }, "v", fakeFetch(429, detail, []));

    expect(result).toEqual({ status: 429, body: detail });
  });

  it.each([{}, { question: 5 }, { question: "" }, { question: "x".repeat(501) }, null, "text"])(
    "rejects a malformed body without calling the backend: %j",
    async (body) => {
      const calls: Call[] = [];

      const result = await forwardAsk(CONFIG, body, "v", fakeFetch(200, {}, calls));

      expect(result.status).toBe(400);
      expect(calls).toHaveLength(0);
    },
  );

  it("sends only the question, whatever else the browser put in the body", async () => {
    const calls: Call[] = [];

    await forwardAsk(CONFIG, { question: "q", admin: true }, "v", fakeFetch(200, {}, calls));

    expect(JSON.parse(String(calls[0].init.body))).toEqual({ question: "q" });
  });

  it("reports an unreachable backend plainly", async () => {
    const down: typeof fetch = async () => {
      throw new TypeError("fetch failed");
    };

    const result = await forwardAsk(CONFIG, { question: "q" }, "v", down);

    expect(result).toEqual({ status: 502, body: { detail: "The backend is not reachable." } });
  });
});

describe("visitorFrom", () => {
  const spoofable = new Headers({ "x-real-ip": "203.0.113.7", "x-forwarded-for": "198.51.100.1" });

  it("uses the address a trusted platform reports", () => {
    expect(visitorFrom(spoofable, true)).toBe("203.0.113.7");
  });

  it("never believes the forwarded list, which starts with the browser's own claim", () => {
    expect(visitorFrom(new Headers({ "x-forwarded-for": "198.51.100.1" }), true)).toBe("shared");
  });

  it("gives everyone one key off the platform, where a browser could choose its address", () => {
    expect(visitorFrom(spoofable, false)).toBe("shared");
    expect(visitorFrom(new Headers(), false)).toBe("shared");
  });
});

describe("rejection", () => {
  const json = { "content-type": "application/json" };

  it("lets the dashboard's own JSON request through", () => {
    expect(rejection(new Headers({ ...json, "sec-fetch-site": "same-origin" }))).toBeNull();
    // Not a browser (curl, a test): no fetch metadata at all.
    expect(rejection(new Headers(json))).toBeNull();
  });

  it.each(["cross-site", "same-site", "none"])("turns away a %s request", (site) => {
    expect(rejection(new Headers({ ...json, "sec-fetch-site": site }))?.status).toBe(403);
  });

  it.each(["text/plain", "application/x-www-form-urlencoded", ""])(
    "turns away a body sent as '%s', which a page could post without a preflight",
    (type) => {
      expect(rejection(new Headers({ "content-type": type }))?.status).toBe(415);
    },
  );

  it("turns away an oversized body before reading it", () => {
    expect(rejection(new Headers({ ...json, "content-length": "5000" }))?.status).toBe(413);
    expect(rejection(new Headers({ ...json, "content-length": "200" }))).toBeNull();
  });
});
