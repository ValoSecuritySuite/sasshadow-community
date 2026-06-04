import { PageHeader } from "@/components/layout/page-header";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Save } from "lucide-react";

export default function SettingsPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        title="Settings"
        description="Configure application preferences and integrations."
      >
        <Button size="sm">
          <Save className="mr-1.5 h-3.5 w-3.5" />
          Save Changes
        </Button>
      </PageHeader>

      <div className="grid gap-6 lg:grid-cols-4">
        <nav className="space-y-1 lg:col-span-1">
          {["General", "API", "Notifications", "Connectors", "Security", "About"].map((item) => (
            <div
              key={item}
              className="rounded-md px-3 py-2 text-sm font-medium text-muted-foreground first:bg-accent first:text-accent-foreground"
            >
              {item}
            </div>
          ))}
        </nav>
        <div className="space-y-6 lg:col-span-3">
          <div className="rounded-xl border bg-card p-6">
            <Skeleton className="mb-1 h-5 w-32" />
            <Skeleton className="mb-6 h-3 w-56" />
            <div className="space-y-4">
              {Array.from({ length: 4 }).map((_, i) => (
                <div key={i} className="space-y-2">
                  <Skeleton className="h-3 w-24" />
                  <Skeleton className="h-10 w-full rounded-md" />
                </div>
              ))}
            </div>
          </div>
          <div className="rounded-xl border bg-card p-6">
            <Skeleton className="mb-1 h-5 w-32" />
            <Skeleton className="mb-6 h-3 w-48" />
            <div className="space-y-4">
              {Array.from({ length: 3 }).map((_, i) => (
                <div key={i} className="flex items-center justify-between">
                  <div className="space-y-1">
                    <Skeleton className="h-4 w-32" />
                    <Skeleton className="h-3 w-48" />
                  </div>
                  <Skeleton className="h-6 w-10 rounded-full" />
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
