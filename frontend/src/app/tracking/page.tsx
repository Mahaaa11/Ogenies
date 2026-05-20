import { Suspense } from "react";
import TrackingClient from "./tracking-client";

export default function TrackingPage() {
  return (
    <Suspense fallback={<div className="text-sm text-zinc-600">Chargement…</div>}>
      <TrackingClient />
    </Suspense>
  );
}

