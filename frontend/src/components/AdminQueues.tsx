"use client";

import React, { useEffect, useState } from "react";
import { apiRequest } from "@/lib/api";
import { inr, formatDateTime } from "@/lib/format";
import { Notice } from "@/components/Notice";

/** Moderation queue (reports) and dispute resolution. Every action is audited on the server. */
export function AdminQueues() {
  const [reports, setReports] = useState<any[]>([]);
  const [disputes, setDisputes] = useState<any[]>([]);
  const [reportStatus, setReportStatus] = useState("under_review");
  const [disputeStatus, setDisputeStatus] = useState("open");
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [msg, setMsg] = useState<{ tone: "success" | "error"; text: string } | null>(null);

  const load = async () => {
    try {
      setReports(await apiRequest<any[]>(`/admin/reports?status=${reportStatus}`));
      setDisputes(await apiRequest<any[]>(`/admin/disputes?status=${disputeStatus}`));
    } catch (e: any) { setMsg({ tone: "error", text: e.message }); }
  };
  useEffect(() => { load(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [reportStatus, disputeStatus]);

  const moderate = async (id: number, action: string) => {
    const n = notes[`r${id}`] || "";
    try { await apiRequest("/admin/moderation", { method: "POST", body: JSON.stringify({ target_type: "report", target_id: id, action, notes: n || null }) }); setMsg({ tone: "success", text: `Report #${id}: ${action}` }); load(); }
    catch (e: any) { setMsg({ tone: "error", text: e.message }); }
  };
  const resolve = async (id: number, decision: string) => {
    const n = notes[`d${id}`] || "";
    if (n.trim().length < 5) return setMsg({ tone: "error", text: "Add a short note (min 5 characters) explaining the decision; it is recorded in the audit log." });
    if (decision === "refund_full" && !confirm("Refund the full amount to the driver? This calls the payment provider.")) return;
    try { await apiRequest(`/admin/disputes/${id}/resolve`, { method: "POST", body: JSON.stringify({ decision, notes: n }) }); setMsg({ tone: "success", text: `Dispute #${id}: ${decision.replace("_", " ")}` }); load(); }
    catch (e: any) { setMsg({ tone: "error", text: e.message }); }
  };
  const btn = "px-2.5 py-1 rounded-lg text-[11px] font-semibold border";

  return (
    <section className="space-y-6" aria-label="Trust and safety queues">
      {msg && <Notice tone={msg.tone}>{msg.text}</Notice>}
      <div className="bg-white rounded-2xl border border-slate-200 p-5 space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-bold text-slate-900">Reports</h2>
          <label className="text-xs text-slate-600">Status <select value={reportStatus} onChange={(e) => setReportStatus(e.target.value)} className="ml-1 border rounded px-2 py-1">{["under_review", "escalated", "resolved", "rejected", "published"].map((s) => <option key={s}>{s}</option>)}</select></label>
        </div>
        {reports.length === 0 && <p className="text-xs text-slate-500">Nothing in this queue.</p>}
        {reports.map((r) => (
          <div key={r.id} className="p-3 rounded-xl bg-slate-50 border border-slate-100 text-xs space-y-1.5">
            <div className="font-semibold text-slate-800">#{r.id} · {r.category.replace(/_/g, " ")} · {r.station_id ? `station ${r.station_id}` : `listing ${r.home_listing_id}`} · evidence level {r.evidence_level}{r.is_verified ? " (verified)" : " (unverified)"}</div>
            {r.description && <p className="text-slate-600">{r.description}</p>}
            {r.evidence?.map((e: any, i: number) => <a key={i} href={e.url} target="_blank" rel="noopener noreferrer nofollow" className="block text-brand-700 underline break-all">{e.type}: {e.url}</a>)}
            <p className="text-slate-400">{formatDateTime(r.created_at)}</p>
            <input aria-label={`Notes for report ${r.id}`} className="w-full border rounded px-2 py-1" placeholder="Moderator notes" value={notes[`r${r.id}`] || ""} onChange={(e) => setNotes({ ...notes, [`r${r.id}`]: e.target.value })} />
            <div className="flex gap-2 flex-wrap">
              <button onClick={() => moderate(r.id, "resolved")} className={`${btn} bg-emerald-50 text-emerald-700 border-emerald-200`}>Resolve (action taken)</button>
              <button onClick={() => moderate(r.id, "rejected")} className={`${btn} bg-slate-100 text-slate-700 border-slate-200`}>Reject</button>
              <button onClick={() => moderate(r.id, "escalated")} className={`${btn} bg-amber-50 text-amber-800 border-amber-200`}>Escalate</button>
            </div>
          </div>
        ))}
      </div>

      <div className="bg-white rounded-2xl border border-slate-200 p-5 space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-bold text-slate-900">Booking & payment disputes</h2>
          <label className="text-xs text-slate-600">Status <select value={disputeStatus} onChange={(e) => setDisputeStatus(e.target.value)} className="ml-1 border rounded px-2 py-1">{["open", "escalated", "resolved", "dismissed"].map((s) => <option key={s}>{s}</option>)}</select></label>
        </div>
        {disputes.length === 0 && <p className="text-xs text-slate-500">Nothing in this queue.</p>}
        {disputes.map((d) => (
          <div key={d.id} className="p-3 rounded-xl bg-slate-50 border border-slate-100 text-xs space-y-1.5">
            <div className="font-semibold text-slate-800">#{d.id} · booking {d.booking_reference} · {d.category} · paid {inr(d.amount_paid)} ({d.payment_status || "no payment"})</div>
            <p className="text-slate-600">{d.reason}</p>
            {d.evidence_url && <a href={d.evidence_url} target="_blank" rel="noopener noreferrer nofollow" className="text-brand-700 underline break-all">{d.evidence_url}</a>}
            {["open", "escalated"].includes(d.status) && (
              <>
                <input aria-label={`Decision notes for dispute ${d.id}`} className="w-full border rounded px-2 py-1" placeholder="Decision notes (required, audited)" value={notes[`d${d.id}`] || ""} onChange={(e) => setNotes({ ...notes, [`d${d.id}`]: e.target.value })} />
                <div className="flex gap-2 flex-wrap">
                  <button onClick={() => resolve(d.id, "refund_full")} className={`${btn} bg-rose-50 text-rose-700 border-rose-200`}>Resolve + full refund</button>
                  <button onClick={() => resolve(d.id, "resolve_no_refund")} className={`${btn} bg-emerald-50 text-emerald-700 border-emerald-200`}>Resolve, no refund</button>
                  <button onClick={() => resolve(d.id, "dismiss")} className={`${btn} bg-slate-100 text-slate-700 border-slate-200`}>Dismiss</button>
                  <button onClick={() => resolve(d.id, "escalate")} className={`${btn} bg-amber-50 text-amber-800 border-amber-200`}>Escalate</button>
                </div>
              </>
            )}
          </div>
        ))}
      </div>
    </section>
  );
}
