"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";

import { ApplicationCard, QueueEmptyState } from "./components";
import type { OfficerApplication } from "./types";

const apiBaseUrl =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const nextApplicationPollingIntervalMs = 15_000;

export default function OfficerDashboard() {
  const [applications, setApplications] = useState<OfficerApplication[]>([]);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [decisionPending, setDecisionPending] = useState<string | null>(null);
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loginPending, setLoginPending] = useState(false);
  const [claimPending, setClaimPending] = useState(false);
  const [isAvailable, setIsAvailable] = useState(false);
  const [showQueue, setShowQueue] = useState(false);
  const claimInFlight = useRef(false);

  useEffect(() => {
    const restoreSession = window.setTimeout(() => {
      setAccessToken(window.sessionStorage.getItem("trust-pass.officer-token"));
    }, 0);
    return () => window.clearTimeout(restoreSession);
  }, []);

  useEffect(() => {
    if (!accessToken) return;

    const restoreAvailability = window.setTimeout(async () => {
      try {
        const response = await fetch(`${apiBaseUrl}/api/v1/auth/me`, {
          headers: { Authorization: `Bearer ${accessToken}` },
        });
        if (!response.ok) throw new Error("Session expired");
        const data = await response.json();
        setIsAvailable(data.is_available ?? false);
      } catch {
        setAccessToken(null);
        window.sessionStorage.removeItem("trust-pass.officer-token");
      }
    }, 0);

    return () => window.clearTimeout(restoreAvailability);
  }, [accessToken]);

  const loadApplications = useCallback(async () => {
    if (!accessToken || !showQueue) return;

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
  }, [accessToken, showQueue]);

  const requestNextApplication = useCallback(async () => {
    if (!accessToken || !isAvailable || claimInFlight.current) return;
    claimInFlight.current = true;
    setClaimPending(true);
    try {
      const response = await fetch(
        `${apiBaseUrl}/api/v1/officer/applications/next`,
        {
          method: "POST",
          headers: { Authorization: `Bearer ${accessToken}` },
        },
      );
      const data = await response.json();
      if (!response.ok)
        throw new Error(data.detail ?? "Unable to assign application.");
      if (!data.available || !data.application) {
        setErrorMessage(null);
        return;
      }
      setApplications((current) => [
        data.application,
        ...current.filter(
          (item) => item.application_id !== data.application.application_id,
        ),
      ]);
      setErrorMessage(null);
    } catch (error) {
      console.error("Application assignment failed:", error);
      setErrorMessage("Unable to assign the next application.");
    } finally {
      claimInFlight.current = false;
      setClaimPending(false);
    }
  }, [accessToken, isAvailable]);

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
      setIsAvailable(data.is_available ?? false);
      setPassword("");
    } catch (error) {
      console.error("Officer login failed:", error);
      setErrorMessage("Invalid officer email or password.");
    } finally {
      setLoginPending(false);
    }
  };

  const handleLogout = () => {
    void fetch(`${apiBaseUrl}/api/v1/officer/availability`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${accessToken}`,
      },
      body: JSON.stringify({ available: false }),
    });
    window.sessionStorage.removeItem("trust-pass.officer-token");
    setAccessToken(null);
    setApplications([]);
  };

  const decideApplication = async (
    applicationId: string,
    decision: "APPROVED" | "REJECTED_IMPROPER" | "REJECTED_TAMPERING",
    note: string,
  ) => {
    const application = applications.find(
      (item) => item.application_id === applicationId,
    );
    if (!application?.claim_token) {
      setErrorMessage("Claim this application before making a decision.");
      return;
    }

    setDecisionPending(applicationId);
    try {
      const response = await fetch(
        `${apiBaseUrl}/api/v1/officer/applications/${applicationId}/decision`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${accessToken}`,
            "X-Claim-Token": application.claim_token,
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
      if (isAvailable) void requestNextApplication();
    } catch (error) {
      console.error("Officer decision failed:", error);
      setErrorMessage("Unable to save the officer decision.");
    } finally {
      setDecisionPending(null);
    }
  };

  const setAvailability = async (available: boolean) => {
    try {
      const response = await fetch(
        `${apiBaseUrl}/api/v1/officer/availability`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${accessToken}`,
          },
          body: JSON.stringify({ available }),
        },
      );
      const data = await response.json();
      if (!response.ok)
        throw new Error(data.detail ?? "Unable to update availability.");
      setIsAvailable(data.available);
    } catch (error) {
      console.error("Availability update failed:", error);
      setErrorMessage("Unable to update availability.");
    }
  };

  const updateLease = async (
    applicationId: string,
    claimToken: string,
    action: "renew" | "release",
  ) => {
    try {
      const response = await fetch(
        `${apiBaseUrl}/api/v1/officer/applications/${applicationId}/${action}`,
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${accessToken}`,
            "X-Claim-Token": claimToken,
          },
        },
      );
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail ?? "Lease update failed.");

      if (action === "release") {
        setApplications((current) =>
          current.filter((item) => item.application_id !== applicationId),
        );
        if (isAvailable) void requestNextApplication();
      } else {
        setApplications((current) =>
          current.map((item) =>
            item.application_id === applicationId
              ? { ...item, lease_expires_at: data.lease_expires_at }
              : item,
          ),
        );
      }
    } catch (error) {
      console.error("Lease update failed:", error);
      setErrorMessage("This application lease is no longer active.");
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

  useEffect(() => {
    if (
      accessToken &&
      isAvailable &&
      !applications.some((item) => item.claim_token)
    ) {
      const initialAssignment = window.setTimeout(
        () => void requestNextApplication(),
        0,
      );
      const assignmentInterval = window.setInterval(
        () => void requestNextApplication(),
        nextApplicationPollingIntervalMs,
      );

      return () => {
        window.clearTimeout(initialAssignment);
        window.clearInterval(assignmentInterval);
      };
    }
  }, [accessToken, applications, isAvailable, requestNextApplication]);

  const visibleApplications = showQueue
    ? applications
    : applications.filter((application) => application.claim_token !== null);

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
          {accessToken && (
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => void setAvailability(!isAvailable)}
                disabled={claimPending}
                className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-700 disabled:opacity-50"
              >
                {isAvailable
                  ? "Available for applications"
                  : "Become available"}
              </button>
              <button
                type="button"
                onClick={() => setShowQueue((current) => !current)}
                className="rounded-lg bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-200"
              >
                {showQueue ? "Hide queue" : "Show queue"}
              </button>
              <button
                type="button"
                onClick={handleLogout}
                className="rounded-lg bg-slate-200 px-4 py-2 text-sm font-semibold text-slate-800 hover:bg-slate-300"
              >
                Sign out
              </button>
            </div>
          )}
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
        ) : visibleApplications.length === 0 ? (
          <QueueEmptyState
            message={
              isAvailable
                ? "No application is currently available."
                : "Turn availability on to receive an application."
            }
          />
        ) : (
          <div className="space-y-6">
            {visibleApplications.map((application) => (
              <ApplicationCard
                key={application.application_id}
                application={application}
                onDecision={decideApplication}
                decisionPending={decisionPending === application.application_id}
                onRelease={(id, token) =>
                  void updateLease(id, token, "release")
                }
                onRenew={(id, token) => void updateLease(id, token, "renew")}
              />
            ))}
          </div>
        )}

        {accessToken && showQueue && (
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
