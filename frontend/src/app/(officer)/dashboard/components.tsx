import type { OfficerApplication, ReviewField } from "./types";
import { useState } from "react";

const fieldLabels: Record<string, string> = {
  date_of_birth: "Date of birth",
  name: "Name",
  expiry: "Expiry date",
  passport_number: "Passport number",
  passport_exists_in_national_repository: "National repository match",
  face_match_score: "Face match score",
  passport_anti_tamper_score: "Passport anti-tamper score",
};

export function ApplicationCard({
  application,
  onDecision,
  decisionPending,
  onRelease,
  onRenew,
}: {
  application: OfficerApplication;
  onDecision: (
    applicationId: string,
    decision: "APPROVED" | "REJECTED_IMPROPER" | "REJECTED_TAMPERING",
    note: string,
  ) => void;
  decisionPending: boolean;
  onRelease: (applicationId: string, claimToken: string) => void;
  onRenew: (applicationId: string, claimToken: string) => void;
}) {
  const [decisionNote, setDecisionNote] = useState("");
  return (
    <article className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
      <header className="flex flex-wrap items-start justify-between gap-4 border-b border-slate-100 p-6">
        <div>
          <p className="font-mono text-xs text-slate-500">
            {application.application_id}
          </p>
          <h2 className="mt-2 text-xl font-semibold text-slate-950">
            Kiosk {application.kiosk_id}
          </h2>
          <p className="mt-1 text-sm text-slate-500">
            Received {new Date(application.created_at).toLocaleString()}
          </p>
        </div>
        <span className="rounded-full bg-amber-100 px-3 py-1 text-xs font-bold text-amber-800">
          {application.status}
        </span>
      </header>

      <div className="grid gap-6 p-6 lg:grid-cols-[minmax(0,1fr)_minmax(320px,0.9fr)]">
        <ImageEvidence application={application} />
        <div>
          <div className="mb-4 flex items-center justify-between">
            <h3 className="text-sm font-bold uppercase tracking-[0.16em] text-slate-500">
              Review checklist
            </h3>
            <span className="text-xs text-slate-400">AI results pending</span>
          </div>
          <div className="divide-y divide-slate-100 rounded-xl border border-slate-200">
            {Object.entries(application.review_fields).map(([key, field]) => (
              <ReviewRow
                key={key}
                label={fieldLabels[key] ?? key}
                field={field}
              />
            ))}
          </div>
        </div>
      </div>

      <details className="border-t border-slate-100 px-6 py-4">
        <summary className="cursor-pointer text-sm font-semibold text-emerald-700">
          View pipeline metadata
        </summary>
        <pre className="mt-3 overflow-auto rounded-lg bg-slate-950 p-4 text-xs text-emerald-200">
          {JSON.stringify(application.result_json, null, 2)}
        </pre>
      </details>

      <footer className="flex flex-wrap items-center justify-between gap-4 border-t border-slate-100 bg-slate-50 px-6 py-4">
        {application.claim_token && (
          <div className="w-full rounded-lg border border-emerald-100 bg-emerald-50 p-3 text-sm text-emerald-800">
            You are reviewing this application. Lease expires at{" "}
            {application.lease_expires_at
              ? new Date(application.lease_expires_at).toLocaleTimeString()
              : "unknown"}
            .
            <div className="mt-2 flex gap-2">
              <button
                type="button"
                disabled={decisionPending}
                onClick={() =>
                  onRenew(application.application_id, application.claim_token!)
                }
                className="rounded-md bg-white px-3 py-1 text-xs font-semibold text-emerald-700 hover:bg-emerald-100"
              >
                Renew lease
              </button>
              <button
                type="button"
                disabled={decisionPending}
                onClick={() =>
                  onRelease(
                    application.application_id,
                    application.claim_token!,
                  )
                }
                className="rounded-md bg-white px-3 py-1 text-xs font-semibold text-slate-700 hover:bg-slate-100"
              >
                Release application
              </button>
            </div>
          </div>
        )}
        <div className="min-w-64 flex-1">
          <label
            htmlFor={`decision-note-${application.application_id}`}
            className="text-xs font-semibold uppercase tracking-wider text-slate-500"
          >
            Decision note
          </label>
          <textarea
            id={`decision-note-${application.application_id}`}
            value={decisionNote}
            onChange={(event) => setDecisionNote(event.target.value)}
            placeholder="Add context for the audit record"
            rows={2}
            maxLength={2000}
            className="mt-2 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none ring-emerald-500 focus:ring-2"
          />
        </div>
        <div className="flex flex-wrap justify-end gap-3">
          <button
            type="button"
            disabled={decisionPending || !application.claim_token}
            onClick={() =>
              onDecision(
                application.application_id,
                "REJECTED_IMPROPER",
                decisionNote,
              )
            }
            className="rounded-lg border border-red-200 px-4 py-2 text-sm font-semibold text-red-700 hover:bg-red-50 disabled:cursor-wait disabled:opacity-50"
          >
            Reject: improper application
          </button>
          <button
            type="button"
            disabled={decisionPending || !application.claim_token}
            onClick={() =>
              onDecision(
                application.application_id,
                "REJECTED_TAMPERING",
                decisionNote,
              )
            }
            className="rounded-lg border border-red-500 bg-red-50 px-4 py-2 text-sm font-semibold text-red-800 hover:bg-red-100 disabled:cursor-wait disabled:opacity-50"
          >
            Reject: tampering risk
          </button>
          <button
            type="button"
            disabled={decisionPending || !application.claim_token}
            onClick={() =>
              onDecision(application.application_id, "APPROVED", decisionNote)
            }
            className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-500 disabled:cursor-wait disabled:opacity-50"
          >
            Approve
          </button>
        </div>
      </footer>
    </article>
  );
}

function ImageEvidence({ application }: { application: OfficerApplication }) {
  return (
    <div>
      <h3 className="mb-4 text-sm font-bold uppercase tracking-[0.16em] text-slate-500">
        Submitted evidence
      </h3>
      <div className="grid gap-4 sm:grid-cols-2">
        <EvidenceImage label="Passport" source={application.passport_image} />
        <EvidenceImage label="Live selfie" source={application.selfie_image} />
      </div>
    </div>
  );
}

function EvidenceImage({
  label,
  source,
}: {
  label: string;
  source: string | null;
}) {
  return (
    <figure>
      <figcaption className="mb-2 text-sm font-semibold text-slate-700">
        {label}
      </figcaption>
      <div className="flex aspect-video items-center justify-center overflow-hidden rounded-xl bg-slate-100">
        {source ? (
          <img
            src={source}
            alt={`${label} submitted evidence`}
            className="h-full w-full object-cover"
          />
        ) : (
          <span className="px-4 text-center text-xs text-slate-400">
            Image unavailable
          </span>
        )}
      </div>
    </figure>
  );
}

function ReviewRow({ label, field }: { label: string; field: ReviewField }) {
  const state =
    field.matched === null ? "AWAITING" : field.matched ? "MATCH" : "FLAG";
  const stateClasses = {
    MATCH: "bg-emerald-50 text-emerald-700",
    FLAG: "bg-red-50 text-red-700",
    AWAITING: "bg-slate-100 text-slate-500",
  };

  return (
    <div className="flex items-center justify-between gap-4 px-4 py-3">
      <span className="text-sm text-slate-600">{label}</span>
      <div className="flex items-center gap-3">
        <span className="text-right text-sm font-semibold text-slate-900">
          {field.value ?? "Not implemented"}
        </span>
        <span
          className={`rounded-full px-2 py-1 text-[10px] font-bold tracking-wider ${stateClasses[state]}`}
        >
          {state}
        </span>
      </div>
    </div>
  );
}

export function QueueEmptyState({ message }: { message: string }) {
  return (
    <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-12 text-center">
      <h2 className="text-lg font-semibold">No applications are waiting</h2>
      <p className="mt-2 text-sm text-slate-500">{message}</p>
    </div>
  );
}
