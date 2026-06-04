import type { Metadata } from "next";
import { Providers } from "@/providers/index";
import { AppShell } from "@/components/layout/app-shell";
import "./globals.css";

export const metadata: Metadata = {
  title: "SaaSShadow.ai — SaaS Security Analysis",
  description: "Detect shadow SaaS integrations, assess risk, and enforce security policies across your organization.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="font-sans antialiased">
        <Providers>
          <AppShell>{children}</AppShell>
        </Providers>
      </body>
    </html>
  );
}
