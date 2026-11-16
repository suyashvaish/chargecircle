"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import {
  Zap,
  MapPin,
  Home,
  CalendarCheck,
  ShieldCheck,
  Wallet,
  ArrowRight,
  Gauge,
  Activity,
  Radio,
} from "lucide-react";
import { apiRequest } from "@/lib/api";
import { PublicStation, HomeListing } from "@/types";
import dynamic from "next/dynamic";

const MapView = dynamic(
  () => import("@/components/MapView").then((m) => m.MapView),
  {
    ssr: false,
    loading: () => (
      <div className="w-full h-full min-h-[480px] bg-slate-100 animate-pulse rounded-2xl flex items-center justify-center text-slate-400 text-sm">
        Loading interactive map engine...
      </div>
    ),
  }
);

const POPULAR_CITIES = [
  { name: "Bengaluru", lat: 12.9716, lng: 77.5946 },
  { name: "Mumbai", lat: 19.076, lng: 72.8777 },
  { name: "Delhi NCR", lat: 28.6139, lng: 77.209 },
];

const WHY_CARDS = [
  {
    icon: CalendarCheck,
    title: "Guaranteed Reserved Slot",
    body: "No more waiting in commercial queues. Book a specific time slot that matches your journey, with arrival access instructions unlocked upon confirmation.",
  },
  {
    icon: ShieldCheck,
    title: "Safety & Verification First",
    body: "Every residential listing confirms licensed electrical earthing, RCBO trip breaker protection, and cable integrity before being approved.",
  },
  {
    icon: Wallet,
    title: "Host Monetization",
    body: "Turn your idle residential EVSE or solar setup into recurring income. Transparent per-kWh rates, parking fees, and automatic Razorpay settlement.",
  },
];

const TIER_CARDS = [
  {
    icon: Activity,
    badge: "Tier 1",
    weight: "Weight: 1.0x",
    title: "Unverified Community Reports",
    body: "Any signed-in driver can submit a free report without making a payment. Protected by 24-hr per-user rate limits and duplicate suppression to prevent manipulation.",
    accent: "text-slate-600 bg-slate-100 border-slate-200",
  },
  {
    icon: Zap,
    badge: "Tier 2",
    weight: "Weight: 3.0x",
    title: "Session-Supported Evidence",
    body: "Elevated credibility given when reports are linked to a completed booking, verified payment, meter photo, or host confirmation.",
    accent: "text-brand-700 bg-brand-50 border-brand-200",
  },
  {
    icon: Radio,
    badge: "Tier 3",
    weight: "Weight: 5.0x",
    title: "Trusted Operational Evidence",
    body: "Live OCPI operator telemetry, official network heartbeat status, or multiple independent non-affiliated verified sessions within the freshness half-life (72h).",
    accent: "text-blue-700 bg-blue-50 border-blue-200",
  },
];

export default function HomePage() {
  const [publicStations, setPublicStations] = useState<PublicStation[]>([]);
  const [homeListings, setHomeListings] = useState<HomeListing[]>([]);
  const [activeCity, setActiveCity] = useState(POPULAR_CITIES[0]);

  useEffect(() => {
    async function loadCityChargers() {
      try {
        const params = new URLSearchParams({
          latitude: String(activeCity.lat),
          longitude: String(activeCity.lng),
          radius_km: "25",
        });

        const [stationResult, listingResult] = await Promise.all([
          apiRequest<PublicStation[]>(`/discovery/stations?${params.toString()}`),
          apiRequest<HomeListing[]>(
            `/marketplace/listings?city=${encodeURIComponent(activeCity.name)}`
          ),
        ]);

        setPublicStations(stationResult);
        setHomeListings(listingResult);
      } catch (err) {
        console.error("Home map load error:", err);
        setPublicStations([]);
        setHomeListings([]);
      }
    }

    loadCityChargers();
  }, [activeCity]);

  return (
    <div className="flex flex-col">
      {/* ============ HERO ============ */}
      <section className="relative overflow-hidden bg-navy-950 text-white">
        {/* Decorative gradients */}
        <div className="absolute inset-0 bg-gradient-to-br from-navy-950 via-navy-900 to-brand-900/60 pointer-events-none" />
        <div className="absolute -top-32 -right-32 w-96 h-96 bg-brand-500/20 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute -bottom-24 -left-24 w-80 h-80 bg-blue-500/10 rounded-full blur-3xl pointer-events-none" />

        <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-20 pb-24 text-center">
          <span className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full text-xs font-semibold tracking-wide uppercase bg-white/10 text-brand-300 border border-brand-400/30 backdrop-blur-sm">
            <Zap className="w-3.5 h-3.5 fill-current" />
            India&apos;s Next-Gen EV Ecosystem
          </span>

          <h1 className="mt-6 text-4xl sm:text-5xl lg:text-6xl font-bold tracking-tight leading-tight max-w-3xl mx-auto">
            Reliable EV Charging,{" "}
            <span className="bg-gradient-to-r from-brand-400 to-emerald-300 bg-clip-text text-transparent">
              Anywhere You Drive.
            </span>
          </h1>

          <p className="mt-6 text-base sm:text-lg text-slate-300 max-w-2xl mx-auto leading-relaxed">
            Discover verified public fast chargers or reserve dedicated private
            residential charging points across Indian cities with real-time
            community confidence scoring.
          </p>

          <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
            <Link
              href="/public-chargers"
              className="inline-flex items-center gap-2 px-6 py-3 rounded-xl bg-brand-600 hover:bg-brand-500 text-white font-semibold shadow-lg shadow-brand-500/25 transition-colors"
            >
              <MapPin className="w-4 h-4" />
              Near Me
            </Link>
            <Link
              href="/marketplace"
              className="inline-flex items-center gap-2 px-6 py-3 rounded-xl bg-white/10 hover:bg-white/20 text-white font-semibold border border-white/20 backdrop-blur-sm transition-colors"
            >
              Explore
              <ArrowRight className="w-4 h-4" />
            </Link>
          </div>

          <div className="mt-8 flex flex-wrap items-center justify-center gap-2 text-sm">
            <span className="text-slate-400 font-medium">Popular Cities:</span>
            {POPULAR_CITIES.map((city) => (
              <button
                key={city.name}
                onClick={() => setActiveCity(city)}
                className={`px-3 py-1.5 rounded-full text-xs font-semibold transition-colors ${
                  activeCity.name === city.name
                    ? "bg-brand-500/20 text-brand-300 border border-brand-400/40"
                    : "bg-white/5 text-slate-300 border border-white/10 hover:bg-white/10"
                }`}
              >
                {city.name}
              </button>
            ))}
          </div>
        </div>
      </section>

      {/* ============ DUAL CTA STRIP ============ */}
      <section className="relative z-10 max-w-5xl mx-auto -mt-12 px-4 sm:px-6 lg:px-8 w-full">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Link
            href="/public-chargers"
            className="group flex items-center gap-4 p-5 rounded-2xl bg-white border border-slate-200 shadow-xl shadow-slate-900/5 hover:border-brand-300 hover:shadow-brand-500/10 transition-all"
          >
            <div className="w-11 h-11 rounded-xl bg-brand-50 border border-brand-200 flex items-center justify-center text-brand-600 shrink-0">
              <Zap className="w-5 h-5 fill-current" />
            </div>
            <div className="min-w-0">
              <p className="font-bold text-slate-900 text-sm">Find Public Fast Charger</p>
              <p className="text-xs text-slate-500 truncate">
                Verified stations near you
              </p>
            </div>
            <ArrowRight className="w-4 h-4 ml-auto text-slate-400 group-hover:text-brand-600 group-hover:translate-x-0.5 transition-all shrink-0" />
          </Link>

          <Link
            href="/host/listings/create"
            className="group flex items-center gap-4 p-5 rounded-2xl bg-white border border-slate-200 shadow-xl shadow-slate-900/5 hover:border-blue-300 hover:shadow-blue-500/10 transition-all"
          >
            <div className="w-11 h-11 rounded-xl bg-blue-50 border border-blue-200 flex items-center justify-center text-blue-600 shrink-0">
              <Home className="w-5 h-5" />
            </div>
            <div className="min-w-0">
              <p className="font-bold text-slate-900 text-sm">Offer Home Charging Bay</p>
              <p className="text-xs text-slate-500 truncate">
                Monetize your wallbox
              </p>
            </div>
            <ArrowRight className="w-4 h-4 ml-auto text-slate-400 group-hover:text-blue-600 group-hover:translate-x-0.5 transition-all shrink-0" />
          </Link>
        </div>
      </section>

      {/* ============ LIVE MAP ============ */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20 w-full">
        <div className="text-center max-w-2xl mx-auto">
          <h2 className="text-3xl sm:text-4xl font-bold tracking-tight text-slate-900">
            Live EV Charging Map{" "}
            <span className="text-brand-600">({activeCity.name})</span>
          </h2>
          <p className="mt-3 text-sm text-slate-500 flex items-center justify-center gap-4">
            <span className="inline-flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-emerald-600 inline-block" />
              Green pins = public fast stations
            </span>
            <span className="inline-flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-blue-600 inline-block" />
              Blue pins = verified residential bays
            </span>
          </p>
        </div>

        <div className="mt-8 rounded-2xl overflow-hidden border border-slate-200 shadow-2xl shadow-slate-900/10 bg-white">
          <div className="h-[420px] sm:h-[480px]">
            <MapView
              publicStations={publicStations}
              homeListings={homeListings}
              center={[activeCity.lat, activeCity.lng]}
              zoom={12}
              className="w-full h-full"
            />
          </div>
        </div>

        <div className="mt-6 text-center">
          <Link
            href="/map"
            className="inline-flex items-center gap-2 px-6 py-3 rounded-xl bg-navy-900 hover:bg-navy-800 text-white text-sm font-semibold shadow-lg transition-colors"
          >
            <MapPin className="w-4 h-4" />
            Expand Full Map View
          </Link>
        </div>
      </section>

      {/* ============ WHY MARKETPLACE ============ */}
      <section className="bg-white border-y border-slate-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
          <div className="text-center max-w-2xl mx-auto">
            <span className="text-xs font-bold uppercase tracking-widest text-brand-600">
              The Peer-to-Peer Revolution
            </span>
            <h2 className="mt-3 text-3xl sm:text-4xl font-bold tracking-tight text-slate-900">
              Why Home Charging Marketplace?
            </h2>
            <p className="mt-4 text-slate-500 leading-relaxed">
              Public chargers are often congested or occupied. ChargeCircle
              allows EV owners with certified wallboxes to open their driveways
              to fellow EV drivers for guaranteed charging slots.
            </p>
          </div>

          <div className="mt-12 grid grid-cols-1 md:grid-cols-3 gap-6">
            {WHY_CARDS.map((card, idx) => (
              <div
                key={card.title}
                className="relative p-6 rounded-2xl bg-slate-50 border border-slate-200 hover:border-brand-300 hover:shadow-lg hover:shadow-brand-500/5 transition-all"
              >
                <span className="absolute top-5 right-6 text-4xl font-black text-slate-200 select-none">
                  {idx + 1}
                </span>
                <div className="w-12 h-12 rounded-xl bg-gradient-to-tr from-brand-600 to-emerald-400 flex items-center justify-center text-white shadow-md shadow-brand-500/20">
                  <card.icon className="w-5 h-5" />
                </div>
                <h3 className="mt-4 text-lg font-bold text-slate-900">{card.title}</h3>
                <p className="mt-2 text-sm text-slate-500 leading-relaxed">{card.body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ============ RELIABILITY ENGINE ============ */}
      <section className="bg-slate-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
          <div className="text-center max-w-2xl mx-auto">
            <span className="inline-flex items-center gap-2 text-xs font-bold uppercase tracking-widest text-slate-500">
              <Gauge className="w-4 h-4 text-brand-600" />
              Algorithmic Integrity
            </span>
            <h2 className="mt-3 text-3xl sm:text-4xl font-bold tracking-tight text-slate-900">
              How Charger Reliability Is Calculated
            </h2>
            <p className="mt-4 text-slate-500 leading-relaxed">
              A successful payment does not automatically prove electricity was
              delivered. We separate payment status from electrical delivery
              through a rigorous three-tier evidence engine.
            </p>
          </div>

          <div className="mt-12 grid grid-cols-1 md:grid-cols-3 gap-6">
            {TIER_CARDS.map((tier) => (
              <div
                key={tier.badge}
                className="p-6 rounded-2xl bg-white border border-slate-200 shadow-sm hover:shadow-lg hover:-translate-y-0.5 transition-all"
              >
                <div className="flex items-center justify-between">
                  <span
                    className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold border ${tier.accent}`}
                  >
                    <tier.icon className="w-3.5 h-3.5" />
                    {tier.badge}
                  </span>
                  <span className="text-xs font-bold text-slate-400 bg-slate-100 px-2.5 py-1 rounded-md">
                    {tier.weight}
                  </span>
                </div>
                <h3 className="mt-4 text-base font-bold text-slate-900">{tier.title}</h3>
                <p className="mt-2 text-sm text-slate-500 leading-relaxed">{tier.body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}