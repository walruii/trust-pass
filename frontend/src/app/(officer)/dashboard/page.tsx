"use client";

import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";

import { ApplicationCard, QueueEmptyState } from "./components";
import type { OfficerApplication } from "./types";

const apiBaseUrl =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export default function OfficerDashboard() {
  const [applications, setApplications] = useState<OfficerApplication[]>([]);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [decisionPending, setDecisionPending] = useState<string | null>(null);
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loginPending, setLoginPending] = useState(false);

  useEffect(() => {
    const restoreSession = window.setTimeout(() => {
      setAccessToken(window.sessionStorage.getItem("trust-pass.officer-token"));
    }, 0);
    return () => window.clearTimeout(restoreSession);
  }, []);

  const loadApplications = useCallback(async () => {
    if (!accessToken) return;

    try {
      const response = await fetch(
        `${apiBaseUrl}/api/v1/officer/applications?application_status=PENDING_AUDIT`,
        {
          cache: "no-store",
          headers: { Authorization: `Bearer ${accessToken}` },
        },
      );
      const data = await response.json();
      if (response.status === 401) {
        setAccessToken(null);
        window.sessionStorage.removeItem("trust-pass.officer-token");
      }
      if (!response.ok)
        throw new Error(data.detail ?? "Unable to load applications.");

      setApplications(data);
      setErrorMessage(null);
    } catch (error) {
      console.error("Officer queue request failed:", error);
      setErrorMessage("Unable to load the officer queue.");
    }
  }, [accessToken]);

  const handleLogin = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setLoginPending(true);
    setErrorMessage(null);

    try {
      const response = await fetch(`${apiBaseUrl}/api/v1/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail ?? "Unable to sign in.");

      window.sessionStorage.setItem(
        "trust-pass.officer-token",
        data.access_token,
      );
      setAccessToken(data.access_token);
      setPassword("");
    } catch (error) {
      console.error("Officer login failed:", error);
      setErrorMessage("Invalid officer email or password.");
    } finally {
      setLoginPending(false);
    }
  };

  const handleLogout = () => {
    window.sessionStorage.removeItem("trust-pass.officer-token");
    setAccessToken(null);
    setApplications([]);
  };

  const decideApplication = async (
    applicationId: string,
    decision: "APPROVED" | "REJECTED_IMPROPER" | "REJECTED_TAMPERING",
    note: string,
  ) => {
    setDecisionPending(applicationId);
    try {
      const response = await fetch(
        `${apiBaseUrl}/api/v1/officer/applications/${applicationId}/decision`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${accessToken}`,
          },
          body: JSON.stringify({ decision, decision_note: note || null }),
        },
      );
      const data = await response.json();
      if (!response.ok)
        throw new Error(data.detail ?? "Unable to save decision.");

      setApplications((current) =>
        current.filter(
          (application) => application.application_id !== applicationId,
        ),
      );
      setErrorMessage(null);
    } catch (error) {
      console.error("Officer decision failed:", error);
      setErrorMessage("Unable to save the officer decision.");
    } finally {
      setDecisionPending(null);
    }
  };

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
            onClick={handleLogout}
            className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-700"
          >
            Sign out
          </button>
        </header>

        {errorMessage && (
          <div className="mb-6 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
            {errorMessage}
          </div>
        )}

        {!accessToken ? (
          <form
            onSubmit={handleLogin}
            className="mx-auto max-w-md rounded-2xl border border-slate-200 bg-white p-8 shadow-sm"
          >
            <h2 className="text-xl font-semibold">Officer sign in</h2>
            <p className="mt-2 text-sm text-slate-500">
              Sign in to view and review pending applications.
            </p>
            <label className="mt-6 block text-sm font-semibold text-slate-700">
              Email
              <input
                type="email"
                required
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                className="mt-2 w-full rounded-lg border border-slate-200 px-3 py-2 font-normal outline-none focus:ring-2 focus:ring-emerald-500"
              />
            </label>
            <label className="mt-4 block text-sm font-semibold text-slate-700">
              Password
              <input
                type="password"
                required
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                className="mt-2 w-full rounded-lg border border-slate-200 px-3 py-2 font-normal outline-none focus:ring-2 focus:ring-emerald-500"
              />
            </label>
            <button
              type="submit"
              disabled={loginPending}
              className="mt-6 w-full rounded-lg bg-emerald-600 px-4 py-3 font-semibold text-white hover:bg-emerald-500 disabled:opacity-50"
            >
              {loginPending ? "Signing in..." : "Sign in"}
            </button>
          </form>
        ) : applications.length === 0 ? (
          <QueueEmptyState />
        ) : (
          <div className="space-y-6">
            {applications.map((application) => (
              <ApplicationCard
                key={application.application_id}
                application={application}
                onDecision={decideApplication}
                decisionPending={decisionPending === application.application_id}
              />
            ))}
          </div>
        )}

        {accessToken && (
          <button
            type="button"
            onClick={() => void loadApplications()}
            className="mt-6 rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-700"
          >
            Refresh queue
          </button>
        )}
      </div>
    </main>
  );
}
