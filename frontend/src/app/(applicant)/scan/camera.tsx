"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import Webcam from "react-webcam";

type ScanStep =
  | "PASSPORT"
  | "SELFIE"
  | "REVIEW"
  | "PROCESSING"
  | "PENDING_AUDIT"
  | "FAILED"
  | "DONE";

type ApplicationStatusResponse = {
  application_id: string;
  status: string;
  error_message?: string | null;
};

const apiBaseUrl =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const applicationStorageKey = "trust-pass.application-id";

export default function CameraScanner() {
  const webcamRef = useRef<Webcam>(null);

  const [step, setStep] = useState<ScanStep>("PASSPORT");
  const [passportImage, setPassportImage] = useState<string | null>(null);
  const [selfieImage, setSelfieImage] = useState<string | null>(null);
  const [applicationId, setApplicationId] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    const restoreApplication = window.setTimeout(() => {
      const savedApplicationId = window.localStorage.getItem(
        applicationStorageKey,
      );

      if (savedApplicationId) {
        setApplicationId(savedApplicationId);
        setStep("PROCESSING");
      }
    }, 0);

    return () => window.clearTimeout(restoreApplication);
  }, []);

  const videoConstraints = {
    width: 1280,
    height: 720,
    facingMode: "user",
  };

  const captureFrame = useCallback(() => {
    return (
      webcamRef.current?.getScreenshot({ width: 1280, height: 720 }) ?? null
    );
  }, []);

  const handlePassportCapture = () => {
    const frame = captureFrame();

    if (frame) {
      setPassportImage(frame);
      setStep("SELFIE");
    }
  };

  const handleSelfieCapture = () => {
    const frame = captureFrame();

    if (frame) {
      setSelfieImage(frame);
      setStep("REVIEW");
    }
  };

  useEffect(() => {
    if (!applicationId) return;

    const controller = new AbortController();
    let cancelled = false;

    const pollStatus = async () => {
      try {
        const response = await fetch(
          `${apiBaseUrl}/api/v1/kiosk/applications/${applicationId}`,
          { signal: controller.signal },
        );
        const data: ApplicationStatusResponse = await response.json();

        if (!response.ok) {
          throw new Error(
            data.error_message ?? "Unable to read application status",
          );
        }

        if (cancelled) return;

        setErrorMessage(data.error_message ?? null);

        if (data.status === "PENDING_AUDIT") {
          setStep("PENDING_AUDIT");
          return;
        }

        if (data.status === "FAILED") {
          setStep("FAILED");
          return;
        }

        setStep("PROCESSING");
        window.setTimeout(pollStatus, 2000);
      } catch (error) {
        if (controller.signal.aborted || cancelled) return;

        console.error("Status polling failed:", error);
        setErrorMessage("Unable to check application status.");
        setStep("FAILED");
      }
    };

    void pollStatus();

    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [applicationId]);

  const handleSubmit = async () => {
    if (!passportImage || !selfieImage) return;

    setStep("PROCESSING");

    try {
      const response = await fetch(`${apiBaseUrl}/api/v1/kiosk/submit`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          passport_base64: passportImage,
          selfie_base64: selfieImage,
          kiosk_id: "GATE_DELHI_01",
        }),
      });

      const data = await response.json();

      if (response.ok && data.application_id) {
        setErrorMessage(null);
        window.localStorage.setItem(applicationStorageKey, data.application_id);
        setApplicationId(data.application_id);
        setStep("PROCESSING");
      } else {
        setErrorMessage(data.detail ?? "Unable to submit application.");
        setStep("REVIEW");
      }
    } catch (err) {
      console.error("Submission failed:", err);
      setErrorMessage("Unable to submit application.");
      setStep("REVIEW");
    }
  };

  const handleRestart = () => {
    setPassportImage(null);
    setSelfieImage(null);
    setErrorMessage(null);
    setStep("PASSPORT");
  };

  const handleForgetApplication = () => {
    window.localStorage.removeItem(applicationStorageKey);
    setPassportImage(null);
    setSelfieImage(null);
    setApplicationId(null);
    setErrorMessage(null);
    setStep("PASSPORT");
  };

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-slate-900 p-6 text-white">
      <div className="mb-6 text-center">
        <h1 className="text-2xl font-bold">
          {step === "PASSPORT" && "Step 1: Position Passport Data Page"}
          {step === "SELFIE" && "Step 2: Position Your Face"}
          {step === "REVIEW" && "Review Your Images"}
          {step === "PROCESSING" && "Verifying Security Credentials..."}
          {step === "PENDING_AUDIT" && "Application Pending Officer Review"}
          {step === "FAILED" && "Application Processing Failed"}
          {step === "DONE" && "Scan Completed Successfully"}
        </h1>
      </div>

      {(step === "PASSPORT" || step === "SELFIE") && (
        <div className="relative aspect-video w-full max-w-xl overflow-hidden rounded-xl border-2 border-slate-700 bg-black shadow-2xl">
          <Webcam
            audio={false}
            ref={webcamRef}
            screenshotFormat="image/jpeg"
            videoConstraints={videoConstraints}
            className="h-full w-full object-cover"
          />

          {step === "PASSPORT" && (
            <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
              <div className="flex h-[75%] w-[85%] flex-col justify-between rounded-lg border-4 border-dashed border-yellow-400 bg-yellow-400/10 p-4">
                <span className="w-max rounded bg-black/60 px-2 py-1 text-xs font-mono uppercase text-yellow-300">
                  Passport Framing Zone
                </span>
                <span className="w-max self-end rounded bg-black/60 px-2 py-1 text-xs font-mono uppercase text-yellow-300">
                  Align MRZ Here ↓
                </span>
              </div>
            </div>
          )}

          {step === "SELFIE" && (
            <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
              <div className="h-[300px] w-[240px] rounded-[50%] border-4 border-dashed border-emerald-400 bg-emerald-400/10" />
            </div>
          )}
        </div>
      )}

      {step === "REVIEW" && passportImage && selfieImage && (
        <div className="w-full max-w-3xl rounded-xl bg-slate-800 p-6">
          <div className="grid gap-6 md:grid-cols-2">
            <div>
              <h2 className="mb-2 font-semibold">Passport</h2>
              <img
                src={passportImage}
                alt="Passport preview"
                className="aspect-video w-full rounded-lg object-cover"
              />
            </div>

            <div>
              <h2 className="mb-2 font-semibold">Selfie</h2>
              <img
                src={selfieImage}
                alt="Selfie preview"
                className="aspect-video w-full rounded-lg object-cover"
              />
            </div>
          </div>

          <div className="mt-6 flex justify-center gap-4">
            <button
              onClick={handleRestart}
              className="rounded-lg bg-slate-700 px-6 py-3 font-semibold hover:bg-slate-600"
            >
              Restart
            </button>
            <button
              onClick={handleSubmit}
              className="rounded-lg bg-emerald-600 px-8 py-3 font-semibold hover:bg-emerald-500"
            >
              Submit
            </button>
          </div>
        </div>
      )}

      {(step === "PROCESSING" || step === "PENDING_AUDIT") && (
        <p className="mb-4 max-w-md text-center text-sm text-amber-300">
          Do not refresh this page. Your application ID is saved so status
          checking can resume if the page reloads.
        </p>
      )}

      {step === "PROCESSING" && (
        <div className="flex flex-col items-center py-12">
          <div className="mb-4 h-16 w-16 animate-spin rounded-full border-4 border-blue-500 border-t-transparent" />
          <p className="text-slate-300">
            Application received. Waiting for verification checks...
          </p>
        </div>
      )}

      {(step === "PENDING_AUDIT" || step === "FAILED") && (
        <div className="max-w-md rounded-xl border border-slate-700 bg-slate-800 p-8 text-center">
          <p className="text-slate-300">
            {step === "PENDING_AUDIT"
              ? "Your application is waiting for an officer review."
              : (errorMessage ?? "Your application could not be processed.")}
          </p>
          {applicationId && (
            <p className="mt-4 break-all text-xs text-slate-500">
              Application ID: {applicationId}
            </p>
          )}
        </div>
      )}

      {step === "DONE" && (
        <div className="max-w-md rounded-xl border border-emerald-500 bg-slate-800 p-8 text-center">
          <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-emerald-500/20 text-2xl font-bold text-emerald-400">
            ✓
          </div>
          <h2 className="mb-2 text-xl font-bold">Submission Received</h2>
          <p className="text-sm text-slate-300">
            Your application is being reviewed by the immigration audit officer.
          </p>
        </div>
      )}

      <div className="mt-6">
        {(step === "PROCESSING" ||
          step === "PENDING_AUDIT" ||
          step === "FAILED") && (
          <button
            onClick={handleForgetApplication}
            className="rounded-lg bg-slate-700 px-6 py-3 font-semibold hover:bg-slate-600"
          >
            Forget Application
          </button>
        )}

        {step === "PASSPORT" && (
          <button
            onClick={handlePassportCapture}
            className="rounded-lg bg-blue-600 px-8 py-3 font-semibold shadow-lg transition-all hover:bg-blue-500"
          >
            Capture Passport Scan
          </button>
        )}

        {step === "SELFIE" && (
          <div className="flex gap-4">
            <button
              onClick={() => setStep("PASSPORT")}
              className="rounded-lg bg-slate-700 px-6 py-3 font-semibold hover:bg-slate-600"
            >
              Back to Passport
            </button>
            <button
              onClick={handleSelfieCapture}
              className="rounded-lg bg-emerald-600 px-8 py-3 font-semibold shadow-lg transition-all hover:bg-emerald-500"
            >
              Take Selfie
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
