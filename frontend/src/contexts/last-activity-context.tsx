"use client";

import * as React from "react";
import type { PipelineResult, DatasetAnalysisResponse } from "@/lib/api/types";

export interface LastActivityState {
  lastScan: PipelineResult | null;
  lastDataset: DatasetAnalysisResponse | null;
}

export interface LastActivityContextValue extends LastActivityState {
  setLastScan: (data: PipelineResult | null) => void;
  setLastDataset: (data: DatasetAnalysisResponse | null) => void;
}

const LastActivityContext = React.createContext<LastActivityContextValue | null>(null);

export function LastActivityProvider({ children }: { children: React.ReactNode }) {
  const [lastScan, setLastScan] = React.useState<PipelineResult | null>(null);
  const [lastDataset, setLastDataset] = React.useState<DatasetAnalysisResponse | null>(null);
  const value = React.useMemo<LastActivityContextValue>(
    () => ({ lastScan, lastDataset, setLastScan, setLastDataset }),
    [lastScan, lastDataset],
  );
  return (
    <LastActivityContext.Provider value={value}>
      {children}
    </LastActivityContext.Provider>
  );
}

export function useLastActivity(): LastActivityContextValue {
  const ctx = React.useContext(LastActivityContext);
  if (!ctx) {
    throw new Error("useLastActivity must be used within LastActivityProvider");
  }
  return ctx;
}

export function useLastActivityOptional(): LastActivityContextValue | null {
  return React.useContext(LastActivityContext);
}
