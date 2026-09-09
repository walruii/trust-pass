"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Webcam from "react-webcam";

import {
  ActiveApplicationNotice,
  CameraCapture,
  ImageReview,
  ProcessingState,
  DecisionState,
  ReviewState,
  ScanHeader,
} from "./components";
import type { ApplicationStatusResponse, ScanStep } from "./types";

const apiBaseUrl =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const applicationStorageKey = "trust-pass.application-id";
const applicationPollingIntervalMs = 15_000;

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
    let pollingTimeout: number | undefined;

    const pollStatus = async () => {
      try {
        const response = await fetch(
          `${apiBaseUrl}/api/v1/kiosk/applications/${applicationId}`,
          { signal: controller.signal },
        );
        const data: ApplicationStatusResponse = await response.json();
        if (!response.ok)
          throw new Error(
            data.error_message ?? "Unable to read application status",
          );
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
        if (data.status === "APPROVED") {
          setStep("DONE");
          return;
        }
        if (
          data.status === "REJECTED_IMPROPER" ||
          data.status === "REJECTED_TAMPERING"
        ) {
          setErrorMessage(data.decision_note ?? null);
          setStep("REJECTED");
          return;
        }

        setStep("PROCESSING");
        pollingTimeout = window.setTimeout(
          pollStatus,
          applicationPollingIntervalMs,
        );
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
      if (pollingTimeout !== undefined) {
        window.clearTimeout(pollingTimeout);
      }
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
        window.localStorage.setItem(applicationStorageKey, data.application_id);
        setErrorMessage(null);
        setApplicationId(data.application_id);
        setStep("PROCESSING");
      } else {
        setErrorMessage(data.detail ?? "Unable to submit application.");
        setStep("REVIEW");
      }
    } catch (error) {
      console.error("Submission failed:", error);
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
    <main className="flex min-h-screen flex-col items-center justify-center bg-slate-100 p-6 text-slate-900">
      <ScanHeader step={step} />
      {(step === "PASSPORT" || step === "SELFIE") && (
        <CameraCapture
          step={step}
          webcamRef={webcamRef}
          onPassportCapture={handlePassportCapture}
          onSelfieCapture={handleSelfieCapture}
          onBack={() => setStep("PASSPORT")}
        />
      )}
      {step === "REVIEW" && passportImage && selfieImage && (
        <ImageReview
          passportImage={passportImage}
          selfieImage={selfieImage}
          onRestart={handleRestart}
          onSubmit={handleSubmit}
        />
      )}
      {(step === "PROCESSING" || step === "PENDING_AUDIT") && (
        <ActiveApplicationNotice applicationId={applicationId} />
      )}
      {step === "PROCESSING" && <ProcessingState />}
      {step === "PENDING_AUDIT" && (
        <ReviewState
          pending
          errorMessage={null}
          applicationId={applicationId}
        />
      )}
      {step === "FAILED" && (
        <ReviewState
          pending={false}
          errorMessage={errorMessage}
          applicationId={applicationId}
        />
      )}
      {step === "DONE" && (
        <DecisionState approved onExit={handleForgetApplication} />
      )}
      {step === "REJECTED" && (
        <DecisionState
          approved={false}
          note={errorMessage}
          onExit={handleForgetApplication}
        />
      )}
      <div className="mt-6">
        {(step === "PROCESSING" ||
          step === "PENDING_AUDIT" ||
          step === "FAILED") && (
          <button
            onClick={handleForgetApplication}
            className="rounded-lg bg-slate-200 px-6 py-3 font-semibold hover:bg-slate-300"
          >
            Forget Application
          </button>
        )}
      </div>
    </main>
  );
}
