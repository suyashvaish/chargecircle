"use client";

import React, { useEffect, useState } from "react";
import { useParams, useSearchParams } from "next/navigation";
import Link from "next/link";
import { MapPin, Zap, ArrowLeft, Star, XCircle, ShieldAlert } from "lucide-react";
import { apiRequest } from "@/lib/api";
import { Booking, User } from "@/types";
import { ReportModal } from "@/components/ReportModal";
import { NavigatePanel } from "@/components/NavigatePanel";
import { Notice } from "@/components/Notice";
import { inr, formatDateTime } from "@/lib/format";

const input = "px-3 py-2 bg-white border border-slate-300 rounded-xl text-sm w-full focus:ring-1 focus:ring-brand-500 focus:outline-none";

export default function BookingDetailPage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const bookingId = Number(params?.id);
  const returnedFromPayment = searchParams?.get("paid") === "1";

  const [me, setMe] = useState<User | null>(null);
  const [booking, setBooking] = useState<Booking | null>(null);
  const [session, setSession] = useState<any>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [msg, setMsg] = useState<{ tone: "success" | "error" | "info"; text: string } | null>(null);
  const [busy, setBusy] = useState(false);

  const [reportOpen, setReportOpen] = useState(false);
  const [meterStart, setMeterStart] = useState("");
  const [energy, setEnergy] = useState("");
  const [meterEnd, setMeterEnd] = useState("");
  const [reviewOpen, setReviewOpen] = useState(false);
  const [reviewComment, setReviewComment] = useState("");
  const [reviewRating, setReviewRating] = useState(5);
  const [cancelOpen, setCancelOpen] = useState(false);
  const [cancelReason, setCancelReason] = useState("");
  const [disputeOpen, setDisputeOpen] = useState(false);
  const [disputeReason, setDisputeReason] = useState("");
  const [disputeCategory, setDisputeCategory] = useState("session");

  const load = async () => {
    if (!bookingId) return;
    try {
      const [b, u] = await Promise.all([apiRequest<Booking>(`/marketplace/bookings/${bookingId}`), apiRequest<User>("/auth/me")]);
      setBooking(b);
      setMe(u);
      setSession(await apiRequest<any>(`/marketplace/bookings/${bookingId}/session`).catch(() => null));
    } catch (err: any) {
      if (err.status !== 404) setLoadError(err.message);
    } finally {
      setIsLoading(false);
    }
  };
  useEffect(() => { load(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [bookingId]);

  const act = async (fn: () => Promise<any>, ok: string) => {
    setBusy(true);
    setMsg(null);
    try {
      const r = await fn();
      setMsg({ tone: "success", text: typeof ok === "function" ? (ok as any)(r) : ok });
      await load();
    } catch (err: any) {
      setMsg({ tone: "error", text: err.message });
    } finally {
      setBusy(false);
    }
  };

  if (isLoading) return <div className="py-24 text-center text-slate-400" aria-busy="true">Loading booking…</div>;
  if (!booking) {
    return (
      <div className="max-w-md mx-auto py-24 text-center px-4 space-y-3">
        <h2 className="text-xl font-bold text-slate-900">Booking Not Found</h2>
        {loadError && <Notice tone="error">{loadError}</Notice>}
        <Link href="/driver/dashboard" className="inline-block text-brand-600 font-semibold text-sm">Return to Dashboard</Link>
      </div>
    );
  }

  const isDriver = me?.id === booking.driver_id;
  const status = booking.status;
  const statusTone: Record<string, string> = {
    confirmed: "bg-emerald-50 text-emerald-700 border border-emerald-200", completed: "bg-blue-50 text-blue-700 border border-blue-200",
    in_progress: "bg-amber-50 text-amber-700 border border-amber-200", cancelled: "bg-slate-100 text-slate-600 border border-slate-200",
    awaiting_payment: "bg-orange-50 text-orange-700 border border-orange-200", disputed: "bg-rose-50 text-rose-700 border border-rose-200",
  };
  const canCancel = ["awaiting_payment", "pending", "confirmed"].includes(status);
  const hoursToStart = (new Date(booking.start_time).getTime() - Date.now()) / 3600000;
  const driverRefundNote = isDriver && status === "confirmed" ? (hoursToStart >= 2 ? "You will get a full refund if you cancel now." : "Less than 2 hours remain: cancelling now will NOT be refunded.") : "";
  const snap = session?.pricing_snapshot;

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      <Link href="/driver/dashboard" className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-500 hover:text-slate-900"><ArrowLeft className="w-4 h-4" aria-hidden="true" />Back to Dashboard</Link>

      {/* Never claim a confirmation the server has not made */}
      {returnedFromPayment && status === "confirmed" && <Notice tone="success" title="Payment verified: booking confirmed">The exact address and access instructions are now unlocked below.</Notice>}
      {returnedFromPayment && status === "awaiting_payment" && <Notice tone="warn" title="Payment not confirmed yet">We have not received confirmation of your payment. If you paid, this page will update shortly; refresh in a minute. Otherwise you can retry before the hold expires.</Notice>}
      {msg && <Notice tone={msg.tone}>{msg.text}</Notice>}

      <div className="bg-white rounded-3xl p-6 sm:p-8 border border-slate-200 shadow-sm space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-100 pb-6">
          <div>
            <span className="text-[11px] font-bold uppercase tracking-wider text-brand-600">Booking {booking.booking_reference}</span>
            <h1 className="text-2xl font-extrabold text-slate-900 mt-1">{booking.listing_title || "Charging Slot Reservation"}</h1>
            <span className="text-xs text-slate-500 block">{formatDateTime(booking.start_time)} → {formatDateTime(booking.end_time)}</span>
            <span className="text-xs text-slate-400">{booking.estimated_kwh} kWh requested · {inr(booking.total_amount)} {booking.payment_status ? `(payment: ${booking.payment_status})` : ""}</span>
          </div>
          <span className={`px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wide ${statusTone[status] || "bg-slate-100 text-slate-700"}`}>{status.replace("_", " ")}</span>
        </div>

        {status === "awaiting_payment" && (
          <Notice tone="warn" title="Awaiting payment">
            Hold expires {formatDateTime(booking.payment_hold_expires_at)}. {isDriver && <Link className="underline font-semibold" href={`/marketplace/${booking.listing_id}`}>Book this charger again</Link>} if the hold has expired.
          </Notice>
        )}
        {status === "cancelled" && <Notice tone="info" title="Cancelled">{booking.cancellation_reason ? `Reason: ${booking.cancellation_reason.replace(/_/g, " ")}. ` : ""}{booking.payment_status === "refunded" ? "Your payment was refunded; banks can take several business days to show it." : booking.payment_status === "captured" ? "Under the cancellation policy no refund applies to this booking." : ""}</Notice>}

        {booking.arrival_instructions_revealed && booking.full_address ? (
          <div className="p-5 rounded-2xl bg-emerald-50/60 border border-emerald-200 space-y-3">
            <div className="flex items-center gap-2 text-emerald-800 font-bold text-sm"><MapPin className="w-4 h-4 text-emerald-600" aria-hidden="true" />Arrival destination</div>
            <p className="text-sm font-semibold text-slate-900">{booking.full_address}</p>
            {booking.parking_access_instructions && <p className="text-xs text-slate-600 pt-2 border-t border-emerald-200/60"><span className="font-semibold text-slate-800">Access:</span> {booking.parking_access_instructions}</p>}
            <NavigatePanel targetType="listing" targetId={booking.listing_id} />
          </div>
        ) : (
          status !== "cancelled" && <Notice tone="info">The exact address is released here once the booking is paid and confirmed.</Notice>
        )}

        <div className="p-5 rounded-2xl bg-slate-50 border border-slate-200 space-y-4">
          <h2 className="text-xs font-bold uppercase tracking-wider text-slate-700 flex items-center gap-2"><Zap className="w-4 h-4 text-brand-600 fill-current" aria-hidden="true" />Charging session</h2>
          {status === "confirmed" && (
            <form className="space-y-2" onSubmit={(e) => { e.preventDefault(); act(() => apiRequest(`/marketplace/bookings/${booking.id}/session/start`, { method: "POST", body: JSON.stringify({ meter_reading_start: meterStart ? Number(meterStart) : null }) }), "Session started."); }}>
              <p className="text-xs text-slate-600">Plug in and start the session. If the charger or a sub-meter shows a reading, note it here (optional).</p>
              <div className="flex gap-2 items-end">
                <label className="text-xs font-semibold text-slate-600 w-48">Meter reading (kWh, optional)<input className={input} type="number" step="0.01" min="0" value={meterStart} onChange={(e) => setMeterStart(e.target.value)} /></label>
                <button disabled={busy} className="px-5 py-2.5 bg-brand-600 hover:bg-brand-700 disabled:opacity-60 text-white font-semibold text-xs rounded-xl">Start session</button>
              </div>
            </form>
          )}
          {status === "in_progress" && (
            <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); act(() => apiRequest(`/marketplace/bookings/${booking.id}/session/complete`, { method: "POST", body: JSON.stringify({ energy_delivered_kwh: Number(energy), meter_reading_end: meterEnd ? Number(meterEnd) : null }) }), "Session recorded."); }}>
              <Notice tone="warn">ChargeCircle cannot read the charger. The energy you enter is a <b>manual entry</b> and is recorded as such, not as a measured value.</Notice>
              <div className="grid grid-cols-2 gap-3">
                <label className="text-xs font-semibold text-slate-600">Energy delivered (kWh)<input required className={input} type="number" step="0.01" min="0.01" value={energy} onChange={(e) => setEnergy(e.target.value)} /></label>
                <label className="text-xs font-semibold text-slate-600">End meter reading (optional)<input className={input} type="number" step="0.01" min="0" value={meterEnd} onChange={(e) => setMeterEnd(e.target.value)} /></label>
              </div>
              <button disabled={busy} className="px-5 py-2.5 bg-blue-600 hover:bg-blue-700 disabled:opacity-60 text-white font-semibold text-xs rounded-xl">Complete & record session</button>
            </form>
          )}
          {(status === "completed" || status === "disputed") && session && snap && (
            <div className="text-xs space-y-1.5 text-slate-700">
              <p><b>{session.energy_delivered_kwh} kWh</b> recorded ({session.verification_source.replace("_", " by ")}, <b>{session.energy_is_measured ? "measured" : "manual entry, not hardware-measured"}</b>); {snap.energy_kwh_estimated} kWh was estimated at booking.</p>
              <p>Recalculated charge at the agreed rates: <b>{inr(snap.final_total)}</b> · amount paid: {inr(snap.amount_paid)}</p>
              <p className="text-slate-500">This is a record only; no automatic adjustment is made to the amount already paid. If it differs materially, open a dispute.</p>
            </div>
          )}
          {status === "completed" && isDriver && <button onClick={() => setReviewOpen(true)} className="px-4 py-2 bg-brand-50 text-brand-700 hover:bg-brand-100 font-semibold text-xs rounded-lg border border-brand-200 inline-flex items-center gap-1.5"><Star className="w-3.5 h-3.5" aria-hidden="true" />Review host experience</button>}
          {!["confirmed", "in_progress", "completed", "disputed"].includes(status) && <p className="text-xs text-slate-500">The session can start once the booking is paid and confirmed.</p>}
        </div>

        <div className="flex flex-wrap gap-3 pt-2">
          {canCancel && <button onClick={() => setCancelOpen(true)} className="px-4 py-2 text-xs font-semibold text-rose-700 bg-rose-50 hover:bg-rose-100 rounded-lg inline-flex items-center gap-1.5"><XCircle className="w-3.5 h-3.5" aria-hidden="true" />Cancel booking</button>}
          {["confirmed", "in_progress", "completed", "cancelled"].includes(status) && booking.payment_status && ["captured", "refunded"].includes(booking.payment_status) && (
            <button onClick={() => setDisputeOpen(true)} className="px-4 py-2 text-xs font-semibold text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-lg inline-flex items-center gap-1.5"><ShieldAlert className="w-3.5 h-3.5" aria-hidden="true" />Open a dispute</button>
          )}
          <button onClick={() => setReportOpen(true)} className="px-4 py-2 text-xs font-semibold text-slate-600 bg-slate-100 hover:bg-slate-200 rounded-lg">Report a problem</button>
        </div>
      </div>

      {cancelOpen && (
        <Dialog title="Cancel this booking?" onClose={() => setCancelOpen(false)}>
          <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); setCancelOpen(false); act(() => apiRequest<any>(`/marketplace/bookings/${booking.id}/cancel`, { method: "POST", body: JSON.stringify({ reason: cancelReason }) }), ((r: any) => r.message) as any); }}>
            <p className="text-xs text-slate-600">Free cancellation up to 2 hours before the start; later cancellations by the driver are not refunded. Host cancellations are always refunded in full.</p>
            {driverRefundNote && <Notice tone={hoursToStart >= 2 ? "success" : "warn"}>{driverRefundNote}</Notice>}
            <label className="block text-xs font-semibold text-slate-700">Reason<input required minLength={3} maxLength={255} className={input} value={cancelReason} onChange={(e) => setCancelReason(e.target.value)} /></label>
            <div className="flex justify-end gap-2"><button type="button" onClick={() => setCancelOpen(false)} className="px-3 py-1.5 text-xs text-slate-600">Keep booking</button><button className="px-4 py-1.5 text-xs font-semibold text-white bg-rose-600 rounded-lg">Cancel booking</button></div>
          </form>
        </Dialog>
      )}

      {disputeOpen && (
        <Dialog title="Open a dispute" onClose={() => setDisputeOpen(false)}>
          <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); setDisputeOpen(false); act(() => apiRequest(`/community/disputes`, { method: "POST", body: JSON.stringify({ booking_id: booking.id, reason: disputeReason, category: disputeCategory }) }), "Dispute opened. Our team will review it and update both parties."); }}>
            <label className="block text-xs font-semibold text-slate-700">Category
              <select className={input} value={disputeCategory} onChange={(e) => setDisputeCategory(e.target.value)}><option value="session">Charging session</option><option value="payment">Payment or refund</option><option value="host_conduct">Host or driver conduct</option><option value="other">Other</option></select></label>
            <label className="block text-xs font-semibold text-slate-700">What happened? (min 15 characters)<textarea required minLength={15} maxLength={3000} rows={4} className={input} value={disputeReason} onChange={(e) => setDisputeReason(e.target.value)} /></label>
            <div className="flex justify-end gap-2"><button type="button" onClick={() => setDisputeOpen(false)} className="px-3 py-1.5 text-xs text-slate-600">Close</button><button className="px-4 py-1.5 text-xs font-semibold text-white bg-brand-600 rounded-lg">Submit dispute</button></div>
          </form>
        </Dialog>
      )}

      {reviewOpen && (
        <Dialog title="Rate your charging session" onClose={() => setReviewOpen(false)}>
          <form className="space-y-4" onSubmit={(e) => { e.preventDefault(); setReviewOpen(false); act(() => apiRequest("/community/reviews", { method: "POST", body: JSON.stringify({ booking_id: booking.id, rating_overall: reviewRating, rating_accuracy: reviewRating, rating_host: reviewRating, rating_parking: reviewRating, comment: reviewComment }) }), "Review submitted. Thank you!"); }}>
            <label className="block text-xs font-semibold text-slate-700">Rating
              <select value={reviewRating} onChange={(e) => setReviewRating(Number(e.target.value))} className={input}>{[5, 4, 3, 2, 1].map((n) => <option key={n} value={n}>{n} / 5</option>)}</select></label>
            <label className="block text-xs font-semibold text-slate-700">Comments (min 10 characters)
              <textarea rows={3} required minLength={10} maxLength={2000} value={reviewComment} onChange={(e) => setReviewComment(e.target.value)} className={input} placeholder="Charger speed, host communication, parking…" /></label>
            <p className="text-[11px] text-slate-400">Reviews show your first name and last initial only. Do not include phone numbers or addresses.</p>
            <div className="flex justify-end gap-2"><button type="button" onClick={() => setReviewOpen(false)} className="px-3 py-1.5 text-xs text-slate-600">Cancel</button><button className="px-4 py-1.5 text-xs font-semibold text-white bg-brand-600 rounded-lg">Submit review</button></div>
          </form>
        </Dialog>
      )}

      <ReportModal isOpen={reportOpen} onClose={() => setReportOpen(false)} homeListingId={booking.listing_id} chargerName="Home Charger" onReportSubmitted={load} />
    </div>
  );
}

function Dialog({ title, onClose, children }: { title: string; onClose: () => void; children: React.ReactNode }) {
  useEffect(() => {
    const h = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [onClose]);
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm" role="dialog" aria-modal="true" aria-label={title}>
      <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-3"><h3 className="text-lg font-bold text-slate-900">{title}</h3>{children}</div>
    </div>
  );
}
