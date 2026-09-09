import Webcam from "react-webcam";
import type { RefObject } from "react";

import type { ScanStep } from "./types";

type CameraCaptureProps = {
  step: "PASSPORT" | "SELFIE";
  webcamRef: RefObject<Webcam | null>;
  onPassportCapture: () => void;
  onSelfieCapture: () => void;
  onBack: () => void;
};

export function ScanHeader({ step }: { step: ScanStep }) {
  const titles: Record<ScanStep, string> = {
    PASSPORT: "Step 1: Position Passport Data Page",
    SELFIE: "Step 2: Position Your Face",
    REVIEW: "Review Your Images",
    PROCESSING: "Verifying Security Credentials...",
    PENDING_AUDIT: "Application Pending Officer Review",
    FAILED: "Application Processing Failed",
    DONE: "Scan Completed Successfully",
  };

  return (
    <div className="mb-6 text-center">
      <p className="mb-2 text-xs font-semibold uppercase tracking-[0.2em] text-emerald-300">
        Trust Pass Applicant Kiosk
      </p>
      <h1 className="text-2xl font-bold">{titles[step]}</h1>
    </div>
  );
}

export function CameraCapture({
  step,
  webcamRef,
  onPassportCapture,
  onSelfieCapture,
  onBack,
}: CameraCaptureProps) {
  return (
    <>
      <div className="relative aspect-video w-full max-w-xl overflow-hidden rounded-xl border border-slate-600 bg-black shadow-2xl">
        <Webcam
          audio={false}
          ref={webcamRef}
          screenshotFormat="image/jpeg"
          videoConstraints={{ width: 1280, height: 720, facingMode: "user" }}
          className="h-full w-full object-cover"
        />

        <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
          {step === "PASSPORT" ? (
            <div className="flex h-[75%] w-[85%] flex-col justify-between rounded-lg border-4 border-dashed border-yellow-400 bg-yellow-400/10 p-4">
              <span className="w-max rounded bg-black/60 px-2 py-1 text-xs font-mono uppercase text-yellow-300">
                Passport Framing Zone
              </span>
              <span className="w-max self-end rounded bg-black/60 px-2 py-1 text-xs font-mono uppercase text-yellow-300">
                Align MRZ Here
              </span>
            </div>
          ) : (
            <div className="h-75 w-60 rounded-[50%] border-4 border-dashed border-emerald-400 bg-emerald-400/10" />
          )}
        </div>
      </div>

      <div className="mt-6 flex gap-4">
        {step === "SELFIE" && (
          <button
            onClick={onBack}
            className="rounded-lg bg-slate-700 px-6 py-3 font-semibold hover:bg-slate-600"
          >
            Back to Passport
          </button>
        )}
        <button
          onClick={step === "PASSPORT" ? onPassportCapture : onSelfieCapture}
          className="rounded-lg bg-emerald-600 px-8 py-3 font-semibold shadow-lg transition-colors hover:bg-emerald-500"
        >
          {step === "PASSPORT" ? "Capture Passport Scan" : "Take Selfie"}
        </button>
      </div>
    </>
  );
}

export function ImageReview({
  passportImage,
  selfieImage,
  onRestart,
  onSubmit,
}: {
  passportImage: string;
  selfieImage: string;
  onRestart: () => void;
  onSubmit: () => void;
}) {
  return (
    <section className="w-full max-w-3xl rounded-2xl border border-slate-200 bg-white p-6 text-slate-900 shadow-sm">
      <div className="grid gap-6 md:grid-cols-2">
        <PreviewImage label="Passport" source={passportImage} />
        <PreviewImage label="Selfie" source={selfieImage} />
      </div>
      <div className="mt-6 flex justify-center gap-4">
        <button
          onClick={onRestart}
          className="rounded-lg bg-slate-700 px-6 py-3 font-semibold hover:bg-slate-600"
        >
          Restart
        </button>
        <button
          onClick={onSubmit}
          className="rounded-lg bg-emerald-600 px-8 py-3 font-semibold hover:bg-emerald-500"
        >
          Submit
        </button>
      </div>
    </section>
  );
}

export function PreviewImage({
  label,
  source,
}: {
  label: string;
  source: string;
}) {
  return (
    <div>
      <h2 className="mb-2 font-semibold text-slate-700">{label}</h2>
      <img
        src={source}
        alt={`${label} preview`}
        className="aspect-video w-full rounded-lg object-cover"
      />
    </div>
  );
}

export function ActiveApplicationNotice({
  applicationId,
}: {
  applicationId: string | null;
}) {
  return (
    <p className="mb-4 max-w-md text-center text-sm text-amber-700">
      Do not refresh this page. Your application ID is saved so status checking
      can resume if the page reloads.
      {applicationId && (
        <span className="mt-2 block break-all text-xs text-slate-500">
          Application ID: {applicationId}
        </span>
      )}
    </p>
  );
}

export function ProcessingState() {
  return (
    <div className="flex flex-col items-center py-12">
      <div className="mb-4 h-16 w-16 animate-spin rounded-full border-4 border-blue-500 border-t-transparent" />
      <p className="text-slate-600">
        Application received. Waiting for verification checks...
      </p>
    </div>
  );
}

export function ReviewState({
  pending,
  errorMessage,
  applicationId,
}: {
  pending: boolean;
  errorMessage: string | null;
  applicationId: string | null;
}) {
  return (
    <div className="max-w-md rounded-2xl border border-slate-200 bg-white p-8 text-center text-slate-900 shadow-sm">
      <p className="text-slate-600">
        {pending
          ? "Your application is waiting for an officer review."
          : (errorMessage ?? "Your application could not be processed.")}
      </p>
      {applicationId && (
        <p className="mt-4 break-all text-xs text-slate-500">
          Application ID: {applicationId}
        </p>
      )}
    </div>
  );
}
