// The browser's only way to the assistant. The admin token is added here, on the
// server, and the reply carries the backend's JSON body and nothing else.
import { backendConfig } from "@/lib/backend";
import { forwardAsk, visitorFrom } from "@/lib/backend-call";

export async function POST(request: Request): Promise<Response> {
  const body: unknown = await request.json().catch(() => null);
  const result = await forwardAsk(backendConfig(), body, visitorFrom(request.headers));
  return Response.json(result.body, { status: result.status });
}
