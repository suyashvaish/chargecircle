
"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import {
  Zap,
  Home,
  Search,
  MapPin,
  ArrowRight,
} from "lucide-react";
import { apiRequest } from "@/lib/api";
import { PublicStation, HomeListing } from "@/types";
import { StatusBadge } from "@/components/StatusBadge";
import dynamic from "next/dynamic";

const MapView = dynamic(
  () => import("@/components/MapView").then((m) => m.MapView),
  {
    ssr: false,
    loading: () => (
      <div className="w-full h-full min-h-[500px] bg-slate-100 animate-pulse rounded-2xl flex items-center justify-center text-slate-400">
        Loading interactive map engine...
      </div>
    ),
  }
);

interface Coordinates {
  latitude: number;
  longitude: number;
}

export default function InteractiveMapPage() {
  const [publicStations, setPublicStations] = useState<PublicStation[]>([]);
  const [homeListings, setHomeListings] = useState<HomeListing[]>([]);

  const [city, setCity] = useState("Noida");
  const [searchInput, setSearchInput] = useState("Noida");

  const [coordinates, setCoordinates] = useState<Coordinates>({
    latitude: 28.5706333,
    longitude: 77.3272147,
  });

  const [activeTab, setActiveTab] = useState<"all" | "public" | "home">("all");
  const [isLoading, setIsLoading] = useState(true);
  const [isSearching, setIsSearching] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    async function loadAllChargers() {
      setIsLoading(true);
      setError("");

      try {
        const params = new URLSearchParams({
          latitude: String(coordinates.latitude),
          longitude: String(coordinates.longitude),
          radius_km: "25",
        });

        const [stationResult, listingResult] = await Promise.all([
          apiRequest<PublicStation[]>(`/discovery/stations?${params.toString()}`),
          apiRequest<HomeListing[]>(
            `/marketplace/listings?city=${encodeURIComponent(city)}`
          ),
        ]);

        setPublicStations(stationResult);
        setHomeListings(listingResult);
      } catch (err) {
        console.error("Map load error:", err);
        setError("Could not load chargers. Please try again.");
      } finally {
        setIsLoading(false);
      }
    }

    loadAllChargers();
  }, [coordinates, city]);

  async function searchCity(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();

    const requestedCity = searchInput.trim();

    if (requestedCity.length < 2) {
      setError("Enter a city or location name.");
      return;
    }

    setIsSearching(true);
    setError("");

    try {
      const result = await apiRequest<Coordinates>(
        `/discovery/geocode?city=${encodeURIComponent(requestedCity)}`
      );

      setCity(requestedCity);
      setCoordinates({
        latitude: result.latitude,
        longitude: result.longitude,
      });
    } catch (err) {
      console.error("Location search failed:", err);
      setError("Location not found. Enter a valid Indian city or locality.");
    } finally {
      setIsSearching(false);
    }
  }

  return (
    <div className="flex flex-col h-[calc(100vh-64px)] overflow-hidden">
      <div className="bg-white border-b border-slate-200 px-4 py-3 flex flex-wrap items-center justify-between gap-3 shrink-0 z-10">
        <div className="flex flex-wrap items-center gap-3">
          <form onSubmit={searchCity} className="flex items-center gap-2">
            <MapPin className="w-4 h-4 text-emerald-600" />

            <input
              type="text"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              placeholder="Enter any Indian city or locality"
              className="w-48 sm:w-64 px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-xs font-semibold text-slate-800"
            />

            <button
              type="submit"
              disabled={isSearching}
              className="px-3 py-2 rounded-lg bg-emerald-600 text-white text-xs font-semibold hover:bg-emerald-700 disabled:opacity-50 flex items-center gap-1"
            >
              <Search className="w-3.5 h-3.5" />
              {isSearching ? "Searching..." : "Search"}
            </button>
          </form>

          <div className="flex rounded-lg border border-slate-200 p-0.5 bg-slate-50 text-xs font-semibold">
            <button
              onClick={() => setActiveTab("all")}
              className={`px-3 py-1 rounded-md transition-colors ${
                activeTab === "all" ? "bg-white text-slate-900 shadow-sm" : "text-slate-500"
              }`}
            >
              All ({publicStations.length + homeListings.length})
            </button>

            <button
              onClick={() => setActiveTab("public")}
              className={`px-3 py-1 rounded-md transition-colors ${
                activeTab === "public" ? "bg-white text-emerald-700 shadow-sm" : "text-slate-500"
              }`}
            >
              Public ({publicStations.length})
            </button>

            <button
              onClick={() => setActiveTab("home")}
              className={`px-3 py-1 rounded-md transition-colors ${
                activeTab === "home" ? "bg-white text-blue-700 shadow-sm" : "text-slate-500"
              }`}
            >
              Home ({homeListings.length})
            </button>
          </div>
        </div>

        <div className="flex items-center gap-2 text-xs text-slate-500">
          <span className="inline-flex items-center gap-1 font-semibold text-emerald-700">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-600 inline-block" />
            Public Fast Hubs
          </span>

          <span className="inline-flex items-center gap-1 font-semibold text-blue-700 ml-2">
            <span className="w-2.5 h-2.5 rounded-full bg-blue-600 inline-block" />
            Residential Bays
          </span>
        </div>
      </div>

      {error && (
        <div className="px-4 py-2 bg-red-50 text-red-700 text-xs border-b border-red-100">
          {error}
        </div>
      )}

      <div className="flex-1 flex flex-col md:flex-row overflow-hidden">
        <div className="flex-1 h-full min-h-[300px]">
          <MapView
            publicStations={activeTab === "home" ? [] : publicStations}
            homeListings={activeTab === "public" ? [] : homeListings}
            center={[coordinates.latitude, coordinates.longitude]}
            zoom={12}
            className="w-full h-full"
          />
        </div>

        <div className="w-full md:w-96 bg-white border-t md:border-t-0 md:border-l border-slate-200 overflow-y-auto p-4 space-y-4 shrink-0 max-h-[45vh] md:max-h-full">
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500">
            Available Chargers in {city}
          </h3>

          {isLoading && (
            <p className="text-xs text-slate-500">Loading chargers...</p>
          )}

          {!isLoading && activeTab !== "home" && publicStations.length === 0 && (
            <p className="text-xs text-slate-500">
              No public chargers found in this area.
            </p>
          )}

          {!isLoading && activeTab !== "public" && homeListings.length === 0 && (
            <p className="text-xs text-slate-500">
              No home charger listings found in this city.
            </p>
          )}

          {activeTab !== "home" &&
            publicStations.map((st) => (
              <div key={st.id} className="p-3.5 rounded-xl border border-slate-200 bg-slate-50 space-y-2 text-xs">
                <div className="flex items-center justify-between">
                  <span className="font-bold text-emerald-700 flex items-center gap-1">
                    <Zap className="w-3.5 h-3.5 fill-current" />
                    {st.operator_name}
                  </span>
                  <StatusBadge status={st.current_status} isSample={st.is_sample} />
                </div>

                <h4 className="font-bold text-slate-900 text-sm leading-snug">
                  {st.name}
                </h4>

                <p className="text-slate-500">{st.address}</p>

                <div className="pt-2 flex justify-between items-center border-t border-slate-200/60">
                  <span className="text-slate-500">
                    {st.connectors_summary[0] || "Fast DC"}
                  </span>

                  <Link
                    href={`/public-chargers/${st.id}`}
                    className="font-semibold text-emerald-700 hover:text-emerald-800 flex items-center gap-1"
                  >
                    View <ArrowRight className="w-3 h-3" />
                  </Link>
                </div>
              </div>
            ))}

          {activeTab !== "public" &&
            homeListings.map((hl) => (
              <div key={hl.id} className="p-3.5 rounded-xl border border-slate-200 bg-blue-50/40 space-y-2 text-xs">
                <div className="flex items-center justify-between">
                  <span className="font-bold text-blue-700 flex items-center gap-1">
                    <Home className="w-3.5 h-3.5" />
                    Residential Bay
                  </span>

                  <span className="font-extrabold text-slate-900">
                    ₹{hl.price_per_kwh}/kWh
                  </span>
                </div>

                <h4 className="font-bold text-slate-900 text-sm leading-snug">
                  {hl.title}
                </h4>

                <p className="text-slate-500">{hl.display_address}</p>

                <div className="pt-2 flex justify-between items-center border-t border-blue-200/50">
                  <span className="text-blue-800 font-semibold">
                    {hl.connector_type} • {hl.power_kw}kW
                  </span>

                  <Link
                    href={`/marketplace/${hl.id}`}
                    className="font-semibold text-blue-700 hover:text-blue-800 flex items-center gap-1"
                  >
                    Reserve <ArrowRight className="w-3 h-3" />
                  </Link>
                </div>
              </div>
            ))}
        </div>
      </div>
    </div>
  );
}
