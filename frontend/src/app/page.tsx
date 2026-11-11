"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  Zap,
  MapPin,
  Search,
  Navigation,
  ShieldCheck,
  Home,
  CheckCircle,
  Clock,
  ArrowRight,
  BatteryCharging,
  DollarSign,
  TrendingUp,
  Award,
} from "lucide-react";
import { apiRequest } from "@/lib/api";
import { PublicStation, HomeListing } from "@/types";
import { StatusBadge } from "@/components/StatusBadge";
import dynamic from "next/dynamic";

// Dynamically import MapView to prevent SSR issues with Leaflet
const MapView = dynamic(() => import("@/components/MapView").then((m) => m.MapView), {
  ssr: false,
  loading: () => (
    <div className="w-full h-[400px] bg-slate-100 animate-pulse rounded-2xl flex items-center justify-center text-slate-400">
      Loading interactive map preview...
    </div>
  ),
});

export default function HomePage() {
  const router = useRouter();
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedCity, setSelectedCity] = useState("Bengaluru");
  const [isLocating, setIsLocating] = useState(false);

  // Live data states
  const [publicStations, setPublicStations] = useState<PublicStation[]>([]);
  const [homeListings, setHomeListings] = useState<HomeListing[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    async function loadInitialData() {
      try {
        const [stations, listings] = await Promise.all([
          apiRequest<PublicStation[]>(`/discovery/stations?city=${selectedCity}`),
          apiRequest<HomeListing[]>(`/marketplace/listings?city=${selectedCity}`),
        ]);
        setPublicStations(stations);
        setHomeListings(listings);
      } catch (err) {
        console.error("Error loading preview data:", err);
      } finally {
        setIsLoading(false);
      }
    }
    loadInitialData();
  }, [selectedCity]);

  const handleUseMyLocation = () => {
    if (!navigator.geolocation) {
      alert("Geolocation is not supported by your browser.");
      return;
    }
    setIsLocating(true);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setIsLocating(false);
        router.push(
          `/public-chargers?lat=${pos.coords.latitude}&lon=${pos.coords.longitude}&radius=20`
        );
      },
      (err) => {
        setIsLocating(false);
        alert("Location access was denied. You can still search by city or landmark.");
      }
    );
  };

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchQuery.trim()) {
      router.push(`/public-chargers?q=${encodeURIComponent(searchQuery.trim())}`);
    } else {
      router.push(`/public-chargers?city=${selectedCity}`);
    }
  };

  return (
    <div className="flex flex-col min-h-screen">
      {/* Hero Section */}
      <section className="relative bg-gradient-to-b from-slate-900 via-slate-900 to-slate-950 text-white pt-16 pb-24 overflow-hidden">
        {/* Subtle background glow */}
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[350px] bg-brand-500/15 blur-[120px] rounded-full pointer-events-none" />

        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10">
          <div className="text-center max-w-3xl mx-auto space-y-4">
            <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-brand-950/80 border border-brand-500/30 text-brand-400 text-xs font-semibold tracking-wide uppercase">
              <Zap className="w-3.5 h-3.5 fill-current" />
              India&apos;s Next-Gen EV Ecosystem
            </div>

            <h1 className="text-4xl sm:text-6xl font-extrabold tracking-tight text-white leading-tight">
              Reliable EV Charging, <br />
              <span className="text-transparent bg-clip-text bg-gradient-to-r from-brand-400 to-emerald-200">
                Anywhere You Drive.
              </span>
            </h1>

            <p className="text-base sm:text-lg text-slate-300 font-normal max-w-2xl mx-auto">
              Discover verified public fast chargers or reserve dedicated private residential charging points across Indian cities with real-time community confidence scoring.
            </p>

            {/* Main Search Box */}
            <div className="mt-8 pt-4">
              <form
                onSubmit={handleSearchSubmit}
                className="bg-white p-2 sm:p-2.5 rounded-2xl shadow-2xl flex flex-col sm:flex-row gap-2 max-w-2xl mx-auto border border-slate-100"
              >
                <div className="flex-1 flex items-center gap-3 px-3 py-2 text-slate-800">
                  <Search className="w-5 h-5 text-slate-400 shrink-0" />
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="Find EV Charging Near You (City, Locality, PIN)"
                    className="w-full bg-transparent text-sm sm:text-base font-medium placeholder-slate-400 focus:outline-none"
                  />
                </div>

                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={handleUseMyLocation}
                    disabled={isLocating}
                    className="flex items-center gap-1.5 px-3.5 py-2.5 rounded-xl text-xs sm:text-sm font-semibold text-slate-700 bg-slate-100 hover:bg-slate-200 transition-colors shrink-0"
                    title="Use Device GPS"
                  >
                    <Navigation className={`w-4 h-4 text-brand-600 ${isLocating ? "animate-spin" : ""}`} />
                    <span className="hidden sm:inline">Near Me</span>
                  </button>

                  <button
                    type="submit"
                    className="flex-1 sm:flex-initial px-6 py-2.5 rounded-xl text-sm font-semibold text-white bg-brand-600 hover:bg-brand-700 shadow-md transition-colors flex items-center justify-center gap-1.5"
                  >
                    Explore
                    <ArrowRight className="w-4 h-4" />
                  </button>
                </div>
              </form>

              {/* City Quick Pills */}
              <div className="flex items-center justify-center gap-2 mt-4 flex-wrap text-xs text-slate-400">
                <span>Popular Cities:</span>
                {["Bengaluru", "Mumbai", "Delhi NCR"].map((city) => (
                  <button
                    key={city}
                    onClick={() => {
                      setSelectedCity(city);
                      setSearchQuery("");
                    }}
                    className={`px-3 py-1 rounded-full border transition-colors ${
                      selectedCity === city
                        ? "bg-brand-500/20 border-brand-400 text-brand-300 font-semibold"
                        : "border-slate-800 hover:border-slate-700 text-slate-300"
                    }`}
                  >
                    {city}
                  </button>
                ))}
              </div>
            </div>

            {/* Dual CTA Actions */}
            <div className="pt-6 flex flex-col sm:flex-row items-center justify-center gap-4">
              <Link
                href="/public-chargers"
                className="w-full sm:w-auto px-6 py-3 rounded-xl bg-slate-800/80 hover:bg-slate-800 border border-slate-700 text-white font-medium text-sm flex items-center justify-center gap-2 shadow-sm transition-colors"
              >
                <Zap className="w-4 h-4 text-brand-400" />
                Find Public Fast Charger
              </Link>
              <Link
                href="/host/listings/create"
                className="w-full sm:w-auto px-6 py-3 rounded-xl bg-brand-600 hover:bg-brand-700 text-white font-semibold text-sm flex items-center justify-center gap-2 shadow-md transition-colors"
              >
                <Home className="w-4 h-4" />
                Offer Home Charging Bay
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* Interactive Map Preview Section */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 -mt-10 mb-16 relative z-20">
        <div className="bg-white rounded-3xl p-4 sm:p-6 shadow-xl border border-slate-200">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-4">
            <div>
              <h2 className="text-xl font-bold text-slate-900 flex items-center gap-2">
                <MapPin className="w-5 h-5 text-brand-600" />
                Live EV Charging Map ({selectedCity})
              </h2>
              <p className="text-xs text-slate-500">
                Green pins denote public fast stations • Blue pins denote verified residential home bays
              </p>
            </div>
            <Link
              href="/map"
              className="text-xs font-semibold text-brand-600 hover:text-brand-700 flex items-center gap-1 self-start sm:self-center"
            >
              Expand Full Map View <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>

          <div className="h-[420px] rounded-2xl overflow-hidden">
            <MapView
              publicStations={publicStations}
              homeListings={homeListings}
              center={
                selectedCity === "Mumbai"
                  ? [19.076, 72.8777]
                  : selectedCity === "Delhi NCR"
                  ? [28.6139, 77.209]
                  : [12.9716, 77.5946]
              }
              zoom={12}
            />
          </div>
        </div>
      </section>

      {/* Priority 2: Home Charging Marketplace Explained */}
      <section className="bg-slate-50 py-16 border-t border-slate-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center max-w-3xl mx-auto mb-12">
            <span className="text-xs font-bold text-brand-600 tracking-wider uppercase">
              The Peer-to-Peer Revolution
            </span>
            <h2 className="text-3xl font-extrabold text-slate-900 mt-2">
              Why Home Charging Marketplace?
            </h2>
            <p className="text-slate-600 mt-3 text-sm sm:text-base">
              Public chargers are often congested or occupied. ChargeCircle allows EV owners with certified wallboxes to open their driveways to fellow EV drivers for guaranteed charging slots.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm space-y-3">
              <div className="w-10 h-10 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center font-bold">
                1
              </div>
              <h3 className="text-lg font-bold text-slate-900">Guaranteed Reserved Slot</h3>
              <p className="text-xs text-slate-600 leading-relaxed">
                No more waiting in commercial queues. Book a specific time slot that matches your journey, with arrival access instructions unlocked upon confirmation.
              </p>
            </div>

            <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm space-y-3">
              <div className="w-10 h-10 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center font-bold">
                2
              </div>
              <h3 className="text-lg font-bold text-slate-900">Safety & Verification First</h3>
              <p className="text-xs text-slate-600 leading-relaxed">
                Every residential listing confirms licensed electrical earthing, RCBO trip breaker protection, and cable integrity before being approved.
              </p>
            </div>

            <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm space-y-3">
              <div className="w-10 h-10 rounded-xl bg-purple-50 text-purple-600 flex items-center justify-center font-bold">
                3
              </div>
              <h3 className="text-lg font-bold text-slate-900">Host Monetization</h3>
              <p className="text-xs text-slate-600 leading-relaxed">
                Turn your idle residential EVSE or solar setup into recurring income. Transparent per-kWh rates, parking fees, and automatic Razorpay settlement.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Priority 3: Charger Trust & Reliability System Explained */}
      <section className="bg-white py-16 border-t border-slate-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center max-w-3xl mx-auto mb-12">
            <span className="text-xs font-bold text-brand-600 tracking-wider uppercase">
              Algorithmic Integrity
            </span>
            <h2 className="text-3xl font-extrabold text-slate-900 mt-2">
              How Charger Reliability Is Calculated
            </h2>
            <p className="text-slate-600 mt-3 text-sm sm:text-base">
              A successful payment does not automatically prove electricity was delivered. We separate payment status from electrical delivery through a rigorous three-tier evidence engine.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="p-6 rounded-2xl bg-slate-50 border border-slate-200 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold px-2.5 py-1 rounded bg-slate-200 text-slate-800">
                  Tier 1
                </span>
                <span className="text-xs text-slate-500">Weight: 1.0x</span>
              </div>
              <h4 className="text-base font-bold text-slate-900">Unverified Community Reports</h4>
              <p className="text-xs text-slate-600 leading-relaxed">
                Any signed-in driver can submit a free report without making a payment. Protected by 24-hr per-user rate limits and duplicate suppression to prevent manipulation.
              </p>
            </div>

            <div className="p-6 rounded-2xl bg-brand-50/50 border border-brand-200 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold px-2.5 py-1 rounded bg-brand-200 text-brand-900">
                  Tier 2
                </span>
                <span className="text-xs text-brand-700 font-semibold">Weight: 3.0x</span>
              </div>
              <h4 className="text-base font-bold text-slate-900">Session-Supported Evidence</h4>
              <p className="text-xs text-slate-600 leading-relaxed">
                Elevated credibility given when reports are linked to a completed booking, verified payment, meter photo, or host confirmation.
              </p>
            </div>

            <div className="p-6 rounded-2xl bg-purple-50/50 border border-purple-200 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold px-2.5 py-1 rounded bg-purple-200 text-purple-900">
                  Tier 3
                </span>
                <span className="text-xs text-purple-700 font-semibold">Weight: 5.0x</span>
              </div>
              <h4 className="text-base font-bold text-slate-900">Trusted Operational Evidence</h4>
              <p className="text-xs text-slate-600 leading-relaxed">
                Live OCPI operator telemetry, official network heartbeat status, or multiple independent non-affiliated verified sessions within the freshness half-life (72h).
              </p>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
