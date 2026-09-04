import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  Outlet,
  Link,
  createRootRouteWithContext,
  useRouter,
  HeadContent,
  Scripts,
} from "@tanstack/react-router";
import { useEffect, type ReactNode } from "react";

import appCss from "../styles.css?url";
import { reportLovableError } from "../lib/lovable-error-reporting";
import { AuthProvider } from "@/context/auth";
import { RunProvider } from "@/context/run";
import { Toaster } from "@/components/ui/sonner";

function NotFoundComponent() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="panel max-w-md p-8 text-center">
        <p className="num text-4xl text-gold">404</p>
        <h2 className="mt-3 font-display text-lg text-foreground">Ledger route not found</h2>
        <p className="mt-2 text-sm text-muted-foreground">
          This control surface does not exist or has been retired.
        </p>
        <div className="mt-6">
          <Link
            to="/"
            className="inline-flex items-center justify-center rounded-sm border border-border bg-surface-raised px-3 py-2 text-sm text-foreground transition-colors duration-150 hover:border-gold hover:text-gold"
          >
            Return to Reconcile
          </Link>
        </div>
      </div>
    </div>
  );
}

function ErrorComponent({ error, reset }: { error: Error; reset: () => void }) {
  console.error(error);
  const router = useRouter();
  useEffect(() => {
    reportLovableError(error, { boundary: "tanstack_root_error_component" });
  }, [error]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="panel max-w-md p-8 text-center">
        <h1 className="font-display text-lg tracking-tight text-risk">
          Control surface failed to load
        </h1>
        <p className="mt-2 text-sm text-muted-foreground">
          The interface hit an unexpected error. Retry, or return to the reconciliation console.
        </p>
        <div className="mt-6 flex flex-wrap justify-center gap-2">
          <button
            onClick={() => {
              router.invalidate();
              reset();
            }}
            className="inline-flex items-center justify-center rounded-sm border border-gold/60 bg-gold/15 px-3 py-2 text-sm text-gold transition-colors duration-150 hover:bg-gold/25"
          >
            Try again
          </button>
          <a
            href="/"
            className="inline-flex items-center justify-center rounded-sm border border-border bg-surface-raised px-3 py-2 text-sm text-foreground transition-colors duration-150 hover:border-gold"
          >
            Reconcile console
          </a>
        </div>
      </div>
    </div>
  );
}

export const Route = createRootRouteWithContext<{ queryClient: QueryClient }>()({
  head: () => ({
    meta: [
      { charSet: "utf-8" },
      { name: "viewport", content: "width=device-width, initial-scale=1" },
      { title: "Ledger Control — AI Finance Controller" },
      {
        name: "description",
        content:
          "Ledger Control reconciles bank statements against gateway ledgers with deterministic and AI matching, exception review, cash forecasting and audit trails.",
      },
      { name: "author", content: "Ledger Control" },
      { property: "og:title", content: "Ledger Control — AI Finance Controller" },
      {
        property: "og:description",
        content:
          "Reconciliation, exception control, cash forecasting and audit for finance operations.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
    links: [
      { rel: "stylesheet", href: appCss },
      { rel: "preconnect", href: "https://fonts.googleapis.com" },
      { rel: "preconnect", href: "https://fonts.gstatic.com", crossOrigin: "anonymous" },
      {
        rel: "stylesheet",
        href: "https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500;600&display=swap",
      },
      { rel: "icon", href: "/favicon.ico", type: "image/x-icon" },
    ],
  }),
  shellComponent: RootShell,
  component: RootComponent,
  notFoundComponent: NotFoundComponent,
  errorComponent: ErrorComponent,
});

function RootShell({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <head>
        <HeadContent />
      </head>
      <body>
        {children}
        <Scripts />
      </body>
    </html>
  );
}

function RootComponent() {
  const { queryClient } = Route.useRouteContext();

  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <RunProvider>
          {/* Required: nested routes render here. Removing <Outlet /> breaks all child routes. */}
          <Outlet />
          <Toaster position="bottom-right" />
        </RunProvider>
      </AuthProvider>
    </QueryClientProvider>
  );
}
