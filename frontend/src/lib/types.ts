// Mirrors the backend's response models (backend/app/lookups.py, main.py, assistant.py).
// Written by hand; backend/tests/test_frontend_contract.py fails if the field names drift.
import type { Window } from "./windows";

export interface ToolUsage {
  tool_id: string;
  tool_name: string;
  headline_event: string;
  headline_count: number;
  active_people: number;
  errors: number;
  headline_count_previous: number | null;
  headline_count_change: number | null;
  active_people_previous: number | null;
  active_people_change: number | null;
  errors_previous: number | null;
  errors_change: number | null;
}

export interface PersonActivity {
  user_id: string;
  name: string;
  client_id: string;
  client_name: string;
  role: string;
  logins: number;
  outputs: number;
  last_seen: string | null;
  logins_previous: number | null;
  logins_change: number | null;
  outputs_previous: number | null;
  outputs_change: number | null;
}

export interface ClientActivity {
  client_id: string;
  client_name: string;
  active_people: number;
  outputs: number;
  active_people_previous: number | null;
  active_people_change: number | null;
  outputs_previous: number | null;
  outputs_change: number | null;
}

export interface ErrorGroup {
  source: string;
  tool_id: string;
  tool_name: string;
  count: number;
  people_affected: number;
  affected: string[];
  count_previous: number | null;
  count_change: number | null;
  people_affected_previous: number | null;
  people_affected_change: number | null;
}

export interface RosterPerson {
  user_id: string;
  name: string;
  client_name: string;
  last_seen: string | null;
}

export interface Roster {
  invited_count: number;
  active_count: number;
  never_showed_up_count: number;
  went_quiet_count: number;
  active: RosterPerson[];
  never_showed_up: RosterPerson[];
  went_quiet: RosterPerson[];
  active_count_previous: number | null;
  active_count_change: number | null;
  went_quiet_count_previous: number | null;
  went_quiet_count_change: number | null;
}

/** One bar of a chart: an hour of today, or a day of a longer window. */
export interface Bucket {
  label: string;
  active_people: number;
  outputs: number;
  errors: number;
  outputs_by_tool: Record<string, number>;
}

/** The series behind the charts, with the window's totals across all tools. */
export interface ActivityOverTime {
  unit: "hour" | "day";
  buckets: Bucket[];
  outputs: number;
  outputs_previous: number;
  outputs_change: number;
  errors: number;
  errors_previous: number;
  errors_change: number;
}

export interface OverviewResponse {
  as_of: string;
  window: Window;
  usage_by_tool: ToolUsage[];
  activity_by_person: PersonActivity[];
  activity_by_client: ClientActivity[];
  roster: Roster;
  trend: ActivityOverTime;
}

export interface ReliabilityResponse {
  as_of: string;
  window: Window;
  errors: ErrorGroup[];
  trend: ActivityOverTime;
}

export interface LookupCalled {
  name: string;
  window: Window;
  args: Record<string, unknown>;
}

export interface AskResponse {
  answer: string;
  window: Window | null;
  lookups_called: LookupCalled[];
  refused: boolean;
  latency_ms: number;
  cost_usd: number;
  demo_mode: boolean;
}

export interface HealthResponse {
  status: string;
  demo_mode: boolean;
}

export interface ErrorBody {
  detail: string;
}
