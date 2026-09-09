export type ScanStep =
  | "PASSPORT"
  | "SELFIE"
  | "REVIEW"
  | "PROCESSING"
  | "PENDING_AUDIT"
  | "FAILED"
  | "DONE";

export type ApplicationStatusResponse = {
  application_id: string;
  status: string;
  error_message?: string | null;
};
