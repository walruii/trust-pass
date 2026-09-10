export type ReviewField = {
  value: string | number | null;
  matched: boolean | null;
  status?: string;
};

export type OfficerApplication = {
  application_id: string;
  kiosk_id: string;
  status: string;
  pipeline_version: string;
  attempt_count: number;
  created_at: string;
  result_json: Record<string, unknown> | null;
  error_message: string | null;
  decision_note: string | null;
  passport_image: string | null;
  selfie_image: string | null;
  review_fields: Record<string, ReviewField>;
  assigned_officer_id: string | null;
  lease_expires_at: string | null;
  claim_token: string | null;
};
