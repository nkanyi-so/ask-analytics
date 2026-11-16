// The only module that reads the admin token. `server-only` makes the build fail if a
// client component ever imports it, so the token cannot reach a browser bundle.
import "server-only";

import { backendGet, type BackendConfig } from "./backend-call";
import type { HealthResponse, OverviewResponse, ReliabilityResponse } from "./types";
import type { Window } from "./windows";

export function backendConfig(): BackendConfig {
  const url = process.env.BACKEND_URL;
  const token = process.env.ADMIN_TOKEN;
  if (!url || !token) {
    throw new Error("BACKEND_URL and ADMIN_TOKEN must be set in the server environment.");
  }
  return { url, token };
}

export function getOverview(window: Window): Promise<OverviewResponse> {
  return backendGet<OverviewResponse>(backendConfig(), `/api/overview?window=${window}`);
}

export function getReliability(window: Window): Promise<ReliabilityResponse> {
  return backendGet<ReliabilityResponse>(backendConfig(), `/api/reliability?window=${window}`);
}

export function getHealth(): Promise<HealthResponse> {
  return backendGet<HealthResponse>(backendConfig(), "/health");
}
