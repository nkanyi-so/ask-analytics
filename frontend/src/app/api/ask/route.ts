// The browser's only way to the assistant. The admin token is added here, on the
// server, and the reply carries the backend's JSON body and nothing else.
import { backendConfig } from "@/lib/backend";
import { forwardAsk, rejection, visitorFrom } from "@/lib/backend-call";

export async function POST(request: Request): Promise<Response> {
  const refused = rejection(request.headers);
  if (refused !== null) {
    return Response.json(refused.body, { status: refused.status });
  }
  const body: unknown = await request.json().catch(() => null);
  // Vercel sets VERCEL=1 and overwrites x-real-ip with the visitor's address.
  const visitor = visitorFrom(request.headers, process.env.VERCEL === "1");
  const result = await forwardAsk(backendConfig(), body, visitor);
  return Response.json(result.body, { status: result.status });
}
