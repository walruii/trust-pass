"use client";

import { useCallback, useEffect, useState } from "react";

import { ApplicationCard, QueueEmptyState } from "./components";
import type { OfficerApplication } from "./types";

const apiBaseUrl =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export default function OfficerDashboard() {
  const [applications, setApplications] = useState<OfficerApplication[]>([]);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const loadApplications = useCallback(async () => {
    try {
      const response = await fetch(
        `${apiBaseUrl}/api/v1/officer/applications?application_status=PENDING_AUDIT`,
        { cache: "no-store" },
      );
      const data = await response.json();
      if (!response.ok)
        throw new Error(data.detail ?? "Unable to load applications.");

      setApplications(data);
      setErrorMessage(null);
    } catch (error) {
      console.error("Officer queue request failed:", error);
      setErrorMessage("Unable to load the officer queue.");
    }
  }, []);

  useEffect(() => {
    const initialLoad = window.setTimeout(() => void loadApplications(), 0);
    const interval = window.setInterval(() => void loadApplications(), 3000);
    return () => {
      window.clearTimeout(initialLoad);
      window.clearInterval(interval);
    };
  }, [loadApplications]);

  return (
    <main className="min-h-screen bg-slate-100 px-6 py-10 text-slate-900">
      <div className="mx-auto max-w-7xl">
        <header className="mb-8 flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="text-sm font-semibold uppercase tracking-[0.2em] text-emerald-700">
              Trust Pass Officer Portal
            </p>
            <h1 className="mt-2 text-3xl font-bold tracking-tight">
              Applications pending audit
            </h1>
            <p className="mt-2 text-sm text-slate-500">
              Review submitted evidence and automated flags before making a
              decision.
            </p>
          </div>
          <button
            type="button"
            onClick={() => void loadApplications()}
            className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-700"
          >
            Refresh queue
          </button>
        </header>

        {errorMessage && (
          <div className="mb-6 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
            {errorMessage}
          </div>
        )}

        {applications.length === 0 ? (
          <QueueEmptyState />
        ) : (
          <div className="space-y-6">
            {applications.map((application) => (
              <ApplicationCard
                key={application.application_id}
                application={application}
              />
            ))}
          </div>
        )}
      </div>
    </main>
  );
}
