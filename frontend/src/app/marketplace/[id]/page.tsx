"use client";

import React, { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  Home,
  MapPin,
  ShieldCheck,
  Zap,
  Clock,
  Calendar,
  Lock,
  Star,
  CheckCircle,
  ArrowLeft,
  DollarSign,
  AlertCircle,
} from "lucide-react";
import { apiRequest } from "@/lib/api";
import { HomeListing, Estimate } from "@/types";
import { inr } from "@/lib/format";
import { NavigatePanel } from "@/components/NavigatePanel";
import { Notice } from "@/components/Notice";

export default function HomeListingDetailPage() {
  const params = useParams();
  const router = useRouter();
  const listingId = Number(params?.id);

  const [listing, setListing] = useState<HomeListing | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [est, setEst] = useState<Estimate | null>(null);

  // Booking Form State
  const [bookingDate, setBookingDate] = useState(() => {
    const d = new Date();
    d.setDate(d.getDate() + 1);
    return d.toISOString().split("T")[0];
  });
  const [startTime, setStartTime] = useState("10:00");
  const [durationHours, setDurationHours] = useState(2);
  const [estimatedKwh, setEstimatedKwh] = useState(15);

  useEffect(() => {
    async function loadListing() {
      if (!listingId) return;
      try {
        const data = await apiRequest<HomeListing>(`/marketplace/listings/${listingId}`);
        setListing(data);
      } catch (err: any) {
        if (err.status !== 404) setLoadError(err.message);
      } finally {
        setIsLoading(false);
      }
    }
    loadListing();
  }, [listingId]);

  // Price shown here comes from the server's own calculation, so it always equals what checkout will charge.
  useEffect(() => {
    if (!listingId) return;
    const t = setTimeout(() => {
      apiRequest<Estimate>("/pricing/estimate", {
        method: "POST",
        body: JSON.stringify({ target_type: "listing", target_id: listingId, energy_kwh: estimatedKwh, hours: durationHours }),
      }).then(setEst).catch(() => setEst(null));
    }, 250);
    return () => clearTimeout(t);
  }, [listingId, estimatedKwh, durationHours]);

  if (isLoading) {
    return <div className="py-24 text-center text-slate-400">Loading home charging bay...</div>;
  }

  if (!listing) {
    return (
      <div className="max-w-xl mx-auto py-24 px-4 text-center">
        <h2 className="text-xl font-bold text-slate-900">Listing Not Found</h2>
        {loadError && <div className="mt-3 text-left"><Notice tone="error">{loadError}</Notice></div>}
        <Link href="/marketplace" className="mt-4 inline-block text-brand-600 font-semibold text-sm">
          &larr; Return to Marketplace
        </Link>
      </div>
    );
  }

  const handleProceedToReserve = () => {
    // Slot times are entered in India Standard Time (the host's availability is also IST).
    const startMs = new Date(`${bookingDate}T${startTime}:00+05:30`).getTime();
    const startDateTime = new Date(startMs).toISOString();
    const endDateTime = new Date(startMs + durationHours * 3600 * 1000).toISOString();

    router.push(
      `/checkout/${listing.id}?start=${encodeURIComponent(startDateTime)}&end=${encodeURIComponent(
        endDateTime
      )}&kwh=${estimatedKwh}`
    );
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      <Link
        href="/marketplace"
        className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-500 hover:text-slate-900"
      >
        <ArrowLeft className="w-4 h-4" />
        Back to Home Marketplace
      </Link>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Main Details (2 cols) */}
        <div className="lg:col-span-2 space-y-8">
          {/* Cover & Gallery */}
          <div className="rounded-3xl overflow-hidden bg-slate-900 h-72 sm:h-96 relative border border-slate-200">
            <img
              src={
                listing.cover_photo_url ||
                "https://images.unsplash.com/photo-1593941707882-a5bba14938c7?auto=format&fit=crop&w=1200&q=80"
              }
              alt={listing.title}
              className="w-full h-full object-cover"
            />
            <div className="absolute top-4 left-4 bg-white/95 backdrop-blur-sm text-blue-700 px-3 py-1.5 rounded-lg text-xs font-bold shadow-md">
              {listing.connector_type} • {listing.power_kw} kW {listing.current_type}
            </div>
          </div>

          {/* Title & Host info */}
          <div className="bg-white rounded-3xl p-6 sm:p-8 border border-slate-200 shadow-sm space-y-6">
            <div>
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-bold uppercase tracking-wider text-slate-400">
                  {listing.locality}, {listing.city}
                </span>
                <div className="flex items-center gap-1 text-sm font-bold text-slate-800">
                  <Star className="w-4 h-4 fill-amber-400 text-amber-400" />
                  {listing.average_rating ? `${listing.average_rating} (${listing.total_reviews} review${listing.total_reviews === 1 ? "" : "s"})` : "No reviews yet"}
                </div>
              </div>
              <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900">{listing.title}</h1>
              <p className="text-sm text-slate-600 mt-3 leading-relaxed">{listing.description}</p>
            </div>

            {/* Address privacy: the server decides what this viewer may see */}
            {listing.address_street ? (
              <Notice tone="success" title="Exact address (visible to you as host or booked driver)">
                {listing.address_street}, {listing.locality}, {listing.city}
                {listing.parking_access_instructions && <p className="mt-1">Access: {listing.parking_access_instructions}</p>}
              </Notice>
            ) : (
              <div className="p-4 rounded-2xl bg-amber-50 border border-amber-200 text-xs text-amber-800 flex items-start gap-3">
                <Lock className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" aria-hidden="true" />
                <div>
                  <span className="font-bold">Residential privacy protection:</span>
                  <p className="mt-0.5">
                    Only an approximate area (roughly 300–500 m) is shown. The exact address and access instructions are released after your booking is paid and confirmed.
                  </p>
                </div>
              </div>
            )}
            <NavigatePanel targetType="listing" targetId={listing.id} />

            {/* Safety & Electrical Protocols */}
            <div className="space-y-3 pt-4 border-t border-slate-100">
              <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                <ShieldCheck className="w-4 h-4 text-emerald-600" />
                Verified Safety Checklist
              </h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs text-slate-700">
                <div className="flex items-center gap-2">
                  <CheckCircle className="w-4 h-4 text-emerald-600 shrink-0" />
                  <span>Licensed Earthing Verified (&lt; 2 Ohms)</span>
                </div>
                <div className="flex items-center gap-2">
                  <CheckCircle className="w-4 h-4 text-emerald-600 shrink-0" />
                  <span>Dedicated RCBO Residual Current Breaker</span>
                </div>
                <div className="flex items-center gap-2">
                  <CheckCircle className="w-4 h-4 text-emerald-600 shrink-0" />
                  <span>Sub-metered Electricity Tracking</span>
                </div>
                <div className="flex items-center gap-2">
                  <CheckCircle className="w-4 h-4 text-emerald-600 shrink-0" />
                  <span>Covered Driveway Parking Bay</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Booking Slot Selection Card (1 col) */}
        <div className="lg:col-span-1">
          <div className="bg-white rounded-3xl p-6 border border-slate-200 shadow-lg sticky top-24 space-y-6">
            <div className="flex items-baseline justify-between border-b border-slate-100 pb-4">
              <div>
                <span className="text-2xl font-extrabold text-slate-900">₹{listing.price_per_kwh}</span>
                <span className="text-xs text-slate-500"> / kWh</span>
              </div>
              <span className="text-xs font-semibold px-2 py-0.5 rounded bg-emerald-50 text-emerald-700 border border-emerald-100">
                Slots checked when you book
              </span>
            </div>

            <div className="space-y-4">
              <div>
                <label htmlFor="booking-date" className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1.5">
                  Select Date (IST)
                </label>
                <div className="flex items-center gap-2 px-3 py-2 bg-slate-50 border border-slate-300 rounded-xl text-sm">
                  <Calendar className="w-4 h-4 text-slate-400" />
                  <input
                    id="booking-date"
                    type="date"
                    value={bookingDate}
                    onChange={(e) => setBookingDate(e.target.value)}
                    className="w-full bg-transparent focus:outline-none"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1.5">
                    Start Time
                  </label>
                  <input
                    type="time"
                    value={startTime}
                    onChange={(e) => setStartTime(e.target.value)}
                    className="w-full px-3 py-2 bg-slate-50 border border-slate-300 rounded-xl text-sm focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1.5">
                    Duration
                  </label>
                  <select
                    value={durationHours}
                    onChange={(e) => setDurationHours(Number(e.target.value))}
                    className="w-full px-3 py-2 bg-slate-50 border border-slate-300 rounded-xl text-sm focus:outline-none"
                  >
                    <option value={1}>1 Hour</option>
                    <option value={2}>2 Hours</option>
                    <option value={3}>3 Hours</option>
                    <option value={4}>4 Hours</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1.5">
                  Estimated Energy: {estimatedKwh} kWh
                </label>
                <input
                  type="range"
                  min="5"
                  max="40"
                  step="1"
                  value={estimatedKwh}
                  onChange={(e) => setEstimatedKwh(Number(e.target.value))}
                  className="w-full accent-brand-600"
                />
                <div className="flex justify-between text-[11px] text-slate-400 mt-1">
                  <span>5 kWh (Quick top-up)</span>
                  <span>40 kWh (Full pack)</span>
                </div>
              </div>
            </div>

            {/* Estimate from the server (same calculation checkout uses) */}
            <div className="p-4 rounded-2xl bg-slate-50 border border-slate-200 space-y-2 text-xs" aria-live="polite">
              {est ? (
                <>
                  {est.lines.map((l) => (
                    <div key={l.label} className="flex justify-between text-slate-600">
                      <span>{l.label}<span className="block text-[11px] text-slate-400">{l.basis}</span></span>
                      <span>{inr(l.amount)}</span>
                    </div>
                  ))}
                  <div className="pt-2 border-t border-slate-200 flex justify-between font-bold text-slate-900 text-sm">
                    <span>Estimated total</span>
                    <span>{inr(est.total_known)}</span>
                  </div>
                  <p className="text-[11px] text-slate-400">{est.assumptions[0]}</p>
                </>
              ) : (
                <p className="text-slate-500">Calculating your estimate…</p>
              )}
            </div>

            <button
              onClick={handleProceedToReserve}
              className="w-full py-3 bg-brand-600 hover:bg-brand-700 text-white font-bold text-sm rounded-xl shadow-md transition-colors"
            >
              Proceed to Checkout
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
