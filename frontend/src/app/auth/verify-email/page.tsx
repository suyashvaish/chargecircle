"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { apiRequest } from "@/lib/api";
import { Notice } from "@/components/Notice";

export default function VerifyEmailPage() {
  const [state, setState] = useState<"working" | "ok" | "error">("working");
  const [message, setMessage] = useState("");

  useEffect(() => {
    const token = new URLSearchParams(window.location.search).get("token");
    if (!token) { setState("error"); setMessage("This verification link is incomplete."); return; }
    apiRequest("/auth/verify-email", { method: "POST", body: JSON.stringify({ token }) })
      .then(() => setState("ok"))
      .catch((e) => { setState("error"); setMessage(e.message); });
  }, []);

  return (
    <div className="min-h-[60vh] flex items-center justify-center px-4 py-12">
      <div className="max-w-md w-full bg-white rounded-3xl p-8 border border-slate-200 shadow-xl space-y-4">
        <h1 className="text-2xl font-extrabold text-slate-900">Email verification</h1>
        {state === "working" && <p className="text-sm text-slate-500" aria-busy="true">Verifying your email…</p>}
        {state === "ok" && <Notice tone="success" title="Email verified">Thanks! <Link className="underline font-semibold" href="/driver/dashboard">Go to your dashboard</Link>.</Notice>}
        {state === "error" && <Notice tone="error">{message} Sign in and request a new verification email from your dashboard.</Notice>}
      </div>
    </div>
  );
}
