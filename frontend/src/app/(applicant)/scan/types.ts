export type ScanStep =
  | "PASSPORT"
  | "SELFIE"
  | "REVIEW"
  | "PROCESSING"
  | "PENDING_AUDIT"
  | "FAILED"
  | "DONE"
  | "REJECTED";

export type ApplicationStatusResponse = {
  application_id: string;
  status: string;
  error_message?: string | null;
  decision_note?: string | null;
};
