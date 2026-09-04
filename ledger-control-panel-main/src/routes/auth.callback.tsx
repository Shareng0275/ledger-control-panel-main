import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";
import { tokenStore } from "@/lib/api";
import { useAuth } from "@/context/auth";

export const Route = createFileRoute("/auth/callback")({
  component: OAuthCallbackPage,
});

function OAuthCallbackPage() {
  const navigate = useNavigate();
  const { restoring } = useAuth();
  const [status, setStatus] = useState("Processing OAuth authentication...");

  useEffect(() => {
    if (typeof window === "undefined") return;

    const urlParams = new URLSearchParams(window.location.search);
    const accessToken = urlParams.get("access_token");
    const refreshToken = urlParams.get("refresh_token");
    const rawUser = urlParams.get("user");
    const error = urlParams.get("error");

    if (error) {
      toast.error(decodeURIComponent(error));
      void navigate({ to: "/login", replace: true });
      return;
    }

    if (accessToken) {
      tokenStore.set(accessToken);
      if (refreshToken) {
        tokenStore.setRefreshToken(refreshToken);
      }
      if (rawUser) {
        try {
          tokenStore.setUserRaw(decodeURIComponent(rawUser));
        } catch {
          tokenStore.setUserRaw(rawUser);
        }
      }

      setStatus("Session confirmed! Loading dashboard...");
      toast.success("Successfully authenticated with OAuth provider!");

      // Refresh window state to ensure full AuthContext and layout hydration
      setTimeout(() => {
        window.location.href = "/";
      }, 400);
    } else {
      toast.error("OAuth callback did not provide access tokens.");
      void navigate({ to: "/login", replace: true });
    }
  }, [navigate]);

  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-[#F7F8FA] p-4 text-center">
      <div className="bg-white p-8 rounded-lg shadow-sm border border-gray-200 max-w-sm w-full flex flex-col items-center">
        <Loader2 className="size-8 text-blue-600 animate-spin mb-4" />
        <h2 className="text-base font-semibold text-gray-900">Completing Sign In</h2>
        <p className="text-xs text-gray-500 mt-1">{status}</p>
      </div>
    </div>
  );
}
