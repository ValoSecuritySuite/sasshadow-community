"use client";

import { ThemeProvider } from "@/providers/theme-provider";
import { QueryProvider } from "@/providers/query-provider";
import { LastActivityProvider } from "@/contexts/last-activity-context";
import { ToastProvider } from "@/contexts/toast-context";
import { EditionProvider } from "@/contexts/edition-context";

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <ThemeProvider>
      <QueryProvider>
        <EditionProvider>
          <LastActivityProvider>
            <ToastProvider>
              {children}
            </ToastProvider>
          </LastActivityProvider>
        </EditionProvider>
      </QueryProvider>
    </ThemeProvider>
  );
}
