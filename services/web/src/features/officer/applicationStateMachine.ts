import type { ApplicationState } from "@/api/client";

export const OFFICER_TRANSITION_ACTIONS = [
  "route",
  "review",
  "request_interview",
  "waitlist",
  "approve",
  "deny",
  "reactivate",
  "withdraw",
] as const;

export type OfficerTransitionAction = (typeof OFFICER_TRANSITION_ACTIONS)[number];

export const VALID_OFFICER_TRANSITIONS: Readonly<
  Record<ApplicationState, readonly OfficerTransitionAction[]>
> = {
  submitted: ["route", "withdraw"],
  queued: ["route", "withdraw"],
  claimed: ["review", "withdraw"],
  in_review: ["request_interview", "waitlist", "approve", "deny", "withdraw"],
  interview: ["waitlist", "approve", "deny", "withdraw"],
  waitlisted: ["reactivate", "withdraw"],
  approved: [],
  denied: [],
  withdrawn: [],
};

export type TransitionInputContract = {
  readonly field: "notes" | "reason" | "decision_reason" | "thread_id" | null;
  readonly label: string;
  readonly required: boolean;
  readonly multiline: boolean;
};

export function validOfficerTransitionActions(
  state: ApplicationState,
): readonly OfficerTransitionAction[] {
  return VALID_OFFICER_TRANSITIONS[state] ?? [];
}

export function transitionActionInput(
  action: OfficerTransitionAction,
): TransitionInputContract {
  if (action === "review") {
    return { field: "notes", label: "Notes", required: true, multiline: true };
  }
  if (action === "waitlist") {
    return { field: "reason", label: "Reason", required: true, multiline: true };
  }
  if (action === "approve" || action === "deny") {
    return {
      field: "decision_reason",
      label: "Decision reason",
      required: true,
      multiline: true,
    };
  }
  if (action === "request_interview" || action === "reactivate") {
    return { field: "reason", label: "Reason", required: false, multiline: true };
  }
  if (action === "withdraw") {
    return { field: "notes", label: "Notes", required: false, multiline: true };
  }
  return { field: null, label: "", required: false, multiline: false };
}
