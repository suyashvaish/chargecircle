"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { apiRequest } from "@/lib/api";
import { Notice } from "@/components/Notice";

export default function ResetPasswordPage() {
  const [token, setToken] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);

  useEffect(() => {
    const q = new URLSearchParams(window.location.search);
    setToken(q.get("token") || "");
    setEmail(q.get("email") || "");
  }, []);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (password !== confirm) return setError("The two passwords do not match.");
    setBusy(true);
    try {
      await apiRequest("/auth/password-reset/confirm", { method: "POST", body: JSON.stringify({ email, reset_token: token, new_password: password }) });
      setDone(true);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const input = "w-full px-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-xl text-sm focus:ring-1 focus:ring-brand-500 focus:outline-none";
  return (
    <div className="min-h-[70vh] flex items-center justify-center px-4 py-12">
      <div className="max-w-md w-full bg-white rounded-3xl p-8 border border-slate-200 shadow-xl space-y-5">
        <h1 className="text-2xl font-extrabold text-slate-900">Choose a new password</h1>
        {!token || !email ? (
          <Notice tone="error">This reset link is incomplete. <Link className="underline font-semibold" href="/auth/forgot-password">Request a new one.</Link></Notice>
        ) : done ? (
          <Notice tone="success" title="Password updated">You can now <Link className="underline font-semibold" href="/auth/login">sign in</Link> with your new password.</Notice>
        ) : (
          <form onSubmit={submit} className="space-y-4">
            {error && <Notice tone="error">{error} {error.includes("expired") && <Link className="underline font-semibold" href="/auth/forgot-password">Request a new link.</Link>}</Notice>}
            <label className="block text-xs font-bold text-slate-700">New password (min 8 characters)
              <input type="password" required minLength={8} autoComplete="new-password" className={input} value={password} onChange={(e) => setPassword(e.target.value)} /></label>
            <label className="block text-xs font-bold text-slate-700">Confirm new password
              <input type="password" required minLength={8} autoComplete="new-password" className={input} value={confirm} onChange={(e) => setConfirm(e.target.value)} /></label>
            <button disabled={busy} className="w-full py-3 bg-brand-600 hover:bg-brand-700 disabled:opacity-60 text-white font-bold text-sm rounded-xl">{busy ? "Saving…" : "Update password"}</button>
          </form>
        )}
      </div>
    </div>
  );
}
