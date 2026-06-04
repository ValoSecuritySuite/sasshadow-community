"use client";

import * as React from "react";
import { cn } from "@/lib/utils";
import { CheckCircle2, XCircle, AlertCircle, Info, X } from "lucide-react";

export type ToastVariant = "success" | "error" | "warning" | "info" | "default";

export interface ToastItem {
  id: string;
  variant: ToastVariant;
  title: string;
  description?: string;
  duration?: number;
  createdAt: number;
}

interface ToastContextValue {
  toasts: ToastItem[];
  addToast: (opts: Omit<ToastItem, "id" | "createdAt">) => void;
  removeToast: (id: string) => void;
}

const ToastContext = React.createContext<ToastContextValue | null>(null);

const DEFAULT_DURATION = 5000;

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = React.useState<ToastItem[]>([]);

  const addToast = React.useCallback(
    (opts: Omit<ToastItem, "id" | "createdAt">) => {
      const id = `toast-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
      const item: ToastItem = {
        ...opts,
        id,
        createdAt: Date.now(),
        duration: opts.duration ?? DEFAULT_DURATION,
      };
      setToasts((prev) => [...prev, item]);
      if (item.duration && item.duration > 0) {
        setTimeout(() => {
          setToasts((prev) => prev.filter((t) => t.id !== id));
        }, item.duration);
      }
    },
    [],
  );

  const removeToast = React.useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const value = React.useMemo(
    () => ({ toasts, addToast, removeToast }),
    [toasts, addToast, removeToast],
  );

  return (
    <ToastContext.Provider value={value}>
      {children}
      <ToastTray toasts={toasts} removeToast={removeToast} />
    </ToastContext.Provider>
  );
}

function ToastTray({
  toasts,
  removeToast,
}: {
  toasts: ToastItem[];
  removeToast: (id: string) => void;
}) {
  return (
    <div
      role="region"
      aria-label="Notifications"
      className="pointer-events-none fixed bottom-0 right-0 z-[100] flex max-h-screen w-full max-w-[420px] flex-col gap-2 p-4 sm:bottom-4 sm:right-4 sm:p-0"
    >
      {toasts.map((t) => (
        <ToastItem key={t.id} item={t} onDismiss={() => removeToast(t.id)} />
      ))}
    </div>
  );
}

function ToastItem({ item, onDismiss }: { item: ToastItem; onDismiss: () => void }) {
  const [visible, setVisible] = React.useState(false);
  React.useEffect(() => {
    const t = requestAnimationFrame(() => setVisible(true));
    return () => cancelAnimationFrame(t);
  }, []);

  const icon = {
    success: <CheckCircle2 className="h-5 w-5 text-emerald-600 dark:text-emerald-400" />,
    error: <XCircle className="h-5 w-5 text-destructive" />,
    warning: <AlertCircle className="h-5 w-5 text-amber-600 dark:text-amber-400" />,
    info: <Info className="h-5 w-5 text-primary" />,
    default: null,
  }[item.variant];

  const bg = {
    success: "border-emerald-200 bg-emerald-50/95 dark:border-emerald-900/50 dark:bg-emerald-950/90",
    error: "border-red-200 bg-red-50/95 dark:border-red-900/50 dark:bg-red-950/90",
    warning: "border-amber-200 bg-amber-50/95 dark:border-amber-900/50 dark:bg-amber-950/90",
    info: "border-primary/30 bg-primary/5",
    default: "border-border bg-card/95",
  }[item.variant];

  return (
    <div
      role="alert"
      className={cn(
        "pointer-events-auto flex gap-3 rounded-lg border p-3 shadow-lg transition-all duration-200",
        bg,
        visible ? "translate-x-0 opacity-100" : "translate-x-4 opacity-0",
      )}
    >
      {icon && <span className="shrink-0">{icon}</span>}
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium text-foreground">{item.title}</p>
        {item.description && (
          <p className="mt-0.5 text-xs text-muted-foreground">{item.description}</p>
        )}
      </div>
      <button
        type="button"
        onClick={onDismiss}
        className="shrink-0 rounded p-1 text-muted-foreground hover:bg-black/5 hover:text-foreground dark:hover:bg-white/10"
        aria-label="Dismiss"
      >
        <span className="sr-only">Dismiss</span>
        <X className="h-4 w-4" />
      </button>
    </div>
  );
}

export function useToast() {
  const ctx = React.useContext(ToastContext);
  if (!ctx) {
    return {
      toasts: [] as ToastItem[],
      addToast: () => {},
      removeToast: () => {},
    };
  }
  return ctx;
}
