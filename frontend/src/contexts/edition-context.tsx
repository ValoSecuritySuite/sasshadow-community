"use client";

import * as React from "react";
import { isCommunityEdition, useEdition } from "@/hooks/api/use-edition";

interface EditionContextValue {
  isCommunity: boolean;
  editionLabel: string;
  isLoading: boolean;
}

const EditionContext = React.createContext<EditionContextValue>({
  isCommunity: true,
  editionLabel: "Community Edition",
  isLoading: true,
});

export function EditionProvider({ children }: { children: React.ReactNode }) {
  const { data, isLoading } = useEdition();
  const isCommunity = isCommunityEdition(data);
  const editionLabel = isCommunity ? "Community Edition" : "Enterprise";

  const value = React.useMemo(
    () => ({ isCommunity, editionLabel, isLoading }),
    [isCommunity, editionLabel, isLoading],
  );

  return (
    <EditionContext.Provider value={value}>{children}</EditionContext.Provider>
  );
}

export function useEditionContext() {
  return React.useContext(EditionContext);
}
