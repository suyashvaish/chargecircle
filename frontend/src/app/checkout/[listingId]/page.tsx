"use client";

import React, { useEffect, useRef, useState } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { ShieldCheck, CreditCard, Zap, AlertCircle } from "lucide-react";
import { apiRequest, getToken } from "@/lib/api";
import { Booking, Estimate, HomeListing } from "@/types";
import { inr, formatDateTime } from "@/lib/format";
import { Notice } from "@/components/Notice";

declare global {
  interface Window { Razorpay?: any }
}

function loadRazorpayScript(): Promise<boolean> {
  return new Promise((resolve) => {
    if (window.Razorpay) return resolve(true);
    const s = document.createElement("script");
    s.src = "https://checkout.razorpay.com/v1/checkout.js";
    s.onload = () => resolve(true);
    s.onerror = () => resolve(false);
    document.body.appendChild(s);
  });
}

export default function CheckoutPage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const router = useRouter();

  const listingId = Number(params?.listingId);
  const startTime = searchParams?.get("start");
  const endTime = searchParams?.get("end");
  const estimatedKwh = Number(searchParams?.get("kwh") || 15);

  const [listing, setListing] = useState<HomeListing | null>(null);
  const [est, setEst] = useState<Estimate | null>(null);
  const [booking, setBooking] = useState<Booking | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isProcessing, setIsProcessing] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [infoMessage, setInfoMessage] = useState("");
  const idemKey = useRef(`cc_pay_${Date.now()}_${Math.random().toString(36).slice(2, 10)}`);

  const hours = startTime && endTime ? (new Date(endTime).getTime() - new Date(startTime).getTime()) / 3600000 : 0;

  useEffect(() => {
    if (!getToken()) {
      router.push("/auth/login?redirect=" + encodeURIComponent(window.location.pathname + window.location.search));
      return;
    }
    (async () => {
      try {
        const [l, e] = await Promise.all([
          apiRequest<HomeListing>(`/marketplace/listings/${listingId}`),
          apiRequest<Estimate>("/pricing/estimate", { method: "POST", body: JSON.stringify({ target_type: "listing", target_id: listingId, energy_kwh: estimatedKwh, hours: hours || undefined }) }),
        ]);
        setListing(l);
        setEst(e);
      } catch (err: any) {
        setErrorMessage(err.message || "Failed to load listing for checkout");
      } finally {
        setIsLoading(false);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [listingId]);

  if (isLoading) return <div className="py-24 text-center text-slate-400" aria-busy="true">Loading checkout…</div>;

  if (!listing || !startTime || !endTime) {
    return (
      <div className="max-w-md mx-auto py-24 text-center px-4">
        <AlertCircle className="w-12 h-12 text-rose-500 mx-auto mb-3" aria-hidden="true" />
        <h2 className="text-xl font-bold text-slate-900">Invalid Booking Session</h2>
        <p className="text-sm text-slate-500 mt-1">{errorMessage || "Required time slots or listing details were not specified."}</p>
        <Link href="/marketplace" className="mt-4 inline-block text-brand-600 font-semibold text-sm">Return to Marketplace</Link>
      </div>
    );
  }

  const confirmAndGo = () => router.push(`/bookings/${booking?.id}`);

  const payWithMock = async (orderRes: any) => {
    const sim = await apiRequest<any>("/payments/sandbox/simulate", { method: "POST", body: JSON.stringify({ payment_reference: orderRes.payment_reference }) });
    await apiRequest("/payments/verify", { method: "POST", body: JSON.stringify({ payment_reference: orderRes.payment_reference, ...sim }) });
  };

  const payWithRazorpay = (orderRes: any, b: Booking) =>
    new Promise<void>(async (resolve, reject) => {
      if (!(await loadRazorpayScript())) return reject(new Error("The payment window could not be loaded. Check your connection and try again."));
      const rz = new window.Razorpay({
        key: orderRes.razorpay_key_id, order_id: orderRes.razorpay_order_id, amount: orderRes.amount_paise, currency: "INR",
        name: "ChargeCircle", description: `Booking ${b.booking_reference}`, prefill: { name: orderRes.user_name, email: orderRes.user_email },
        handler: async (resp: any) => {
          try {
            await apiRequest("/payments/verify", { method: "POST", body: JSON.stringify({ payment_reference: orderRes.payment_reference, razorpay_order_id: resp.razorpay_order_id, razorpay_payment_id: resp.razorpay_payment_id, razorpay_signature: resp.razorpay_signature }) });
            resolve();
          } catch (e) { reject(e); }
        },
        modal: { ondismiss: () => reject(new Error("Payment was not completed. Your slot is held for a few minutes; you can try again.")) },
      });
      rz.on("payment.failed", (r: any) => reject(new Error(`Payment failed: ${r?.error?.description || "the bank declined it"}. You have not been charged for a confirmed booking.`)));
      rz.open();
    });

  const handlePay = async () => {
    setIsProcessing(true);
    setErrorMessage("");
    setInfoMessage("");
    try {
      let b = booking;
      if (!b) {
        // The server prices the booking itself; nothing here is trusted for the amount.
        b = await apiRequest<Booking>("/marketplace/bookings", { method: "POST", body: JSON.stringify({ listing_id: listing.id, start_time: startTime, end_time: endTime, estimated_kwh: estimatedKwh }) });
        setBooking(b);
      }
      const orderRes = await apiRequest<any>("/payments/initiate", { method: "POST", body: JSON.stringify({ booking_id: b.id, idempotency_key: idemKey.current }) });
      if (orderRes.mode === "mock") await payWithMock(orderRes);
      else await payWithRazorpay(orderRes, b);
      // Only now, after the server verified the payment, do we go to the confirmed booking.
      router.push(`/bookings/${b.id}?paid=1`);
    } catch (err: any) {
      if (err.status === 409) setErrorMessage("Someone just reserved that time slot. Please go back and choose another time.");
      else setErrorMessage(err.message || "Payment process could not be completed.");
      setIsProcessing(false);
    }
  };

  const total = booking?.total_amount ?? est?.total_known ?? 0;
  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-10 space-y-8">
      <div>
        <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight">Confirm & Pay for Charging Slot</h1>
        <p className="text-xs sm:text-sm text-slate-500 mt-1">Your booking is confirmed only after the payment has been verified by our server.</p>
      </div>

      {errorMessage && <Notice tone="error">{errorMessage}</Notice>}
      {infoMessage && <Notice tone="info">{infoMessage}</Notice>}
      {booking && booking.payment_hold_expires_at && <Notice tone="warn">Slot held until {formatDateTime(booking.payment_hold_expires_at)}. Unpaid holds are released automatically.</Notice>}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
        <div className="md:col-span-2 space-y-6">
          <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm space-y-4">
            <h2 className="text-base font-bold text-slate-900 flex items-center gap-2"><Zap className="w-4 h-4 text-brand-600 fill-current" aria-hidden="true" />Reservation Summary</h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
              <div className="p-3 rounded-xl bg-slate-50 border border-slate-100">
                <span className="text-slate-400 block font-semibold uppercase text-[10px]">Charging Facility</span>
                <span className="font-bold text-slate-800 text-sm">{listing.title}</span>
                <span className="text-slate-500 block mt-0.5">{listing.display_address} (approximate; exact address after payment)</span>
              </div>
              <div className="p-3 rounded-xl bg-slate-50 border border-slate-100">
                <span className="text-slate-400 block font-semibold uppercase text-[10px]">Slot Timing</span>
                <span className="font-bold text-slate-800 text-sm">{formatDateTime(startTime)}</span>
                <span className="text-slate-500 block mt-0.5">Duration: {hours} hours · {estimatedKwh} kWh requested</span>
              </div>
            </div>
          </div>

          <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm space-y-3">
            <h2 className="text-base font-bold text-slate-900 flex items-center gap-2"><CreditCard className="w-4 h-4 text-blue-600" aria-hidden="true" />Payment</h2>
            <p className="text-xs text-slate-600">Payments are processed by Razorpay (UPI, cards, netbanking). You choose your method in the secure payment window; ChargeCircle never sees your card details.</p>
            <Notice tone="info">If this site runs in development mode, a clearly labelled test payment is used instead and no money moves.</Notice>
            <p className="text-[11px] text-slate-500">Cancel free of charge up to 2 hours before the start; later cancellations by the driver are not refunded. If the host cancels you get a full refund.</p>
          </div>
        </div>

        <div className="md:col-span-1">
          <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-md space-y-4 sticky top-24">
            <h2 className="text-sm font-bold text-slate-900 uppercase tracking-wider">Payment Summary</h2>
            <div className="space-y-2.5 text-xs">
              {est?.lines.map((l) => (
                <div key={l.label} className="flex justify-between text-slate-600"><span>{l.label}</span><span>{inr(l.amount)}</span></div>
              ))}
              <div className="pt-3 border-t border-slate-200 flex justify-between font-extrabold text-slate-900 text-base"><span>Amount to Pay</span><span>{inr(total)}</span></div>
              {booking && est && booking.total_amount !== est.total_known && <p className="text-amber-700">The final amount was fixed by the server when you reserved the slot.</p>}
            </div>
            <button onClick={handlePay} disabled={isProcessing} className="w-full py-3 bg-brand-600 hover:bg-brand-700 text-white font-bold text-sm rounded-xl shadow-md transition-all disabled:opacity-50 flex items-center justify-center gap-2">
              <ShieldCheck className="w-4 h-4" aria-hidden="true" />
              {isProcessing ? "Processing…" : booking ? `Retry payment ${inr(total, 0)}` : `Reserve & pay ${inr(total, 0)}`}
            </button>
            <p className="text-[11px] text-slate-400 text-center leading-relaxed">The exact address and access instructions unlock only after your payment is verified.</p>
          </div>
        </div>
      </div>
    </div>
  );
}
