// What one lookup returned, for the working under an answer. Read through the same
// backend endpoints the pages use, with the token added here on the server.
//
// The reply is titled rows of figures and nothing else: no ids, and previous-window
// values only when asked for. Those previous values are the one thing here that the
// tables do not print (they show the change); an answer that compares states them.
import { getOverview, getReliability } from "@/lib/backend";
import { endpointFor, isLookup, rowsOf, type Asked } from "@/lib/evidence";
import { WINDOWS, type Window } from "@/lib/windows";

const ID = /^[a-z0-9_]{1,40}$/;

function windowFrom(value: string | null): Window | null {
  return WINDOWS.find((window) => window === value) ?? null;
}

function idFrom(value: string | null): string | null | undefined {
  if (value === null) return null;
  return ID.test(value) ? value : undefined;
}

export async function GET(request: Request): Promise<Response> {
  // The same courtesy as the Ask route: only the dashboard's own pages call this.
  const site = request.headers.get("sec-fetch-site");
  if (site !== null && site !== "same-origin") {
    return Response.json({ detail: "Read this from the dashboard itself." }, { status: 403 });
  }
  const params = new URL(request.url).searchParams;
  const lookup = params.get("lookup");
  const window = windowFrom(params.get("window"));
  const userId = idFrom(params.get("user_id"));
  const toolId = idFrom(params.get("tool_id"));
  if (!isLookup(lookup) || window === null || userId === undefined || toolId === undefined) {
    return Response.json({ detail: "Unknown lookup, window or filter." }, { status: 400 });
  }
  const asked: Asked = { compared: params.get("previous") === "1", userId, toolId };
  try {
    const body = endpointFor(lookup) === "reliability" ? await getReliability(window) : await getOverview(window);
    return Response.json({ rows: rowsOf(lookup, body, asked) });
  } catch {
    return Response.json({ detail: "The backend is not reachable." }, { status: 502 });
  }
}
