"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { Zap, Search, MapPin, ArrowRight, LocateFixed, Scale } from "lucide-react";
import { apiRequest, getToken } from "@/lib/api";
import { PublicStation, ProviderMeta, Vehicle } from "@/types";
import { StatusBadge } from "@/components/StatusBadge";
import { DataBadge } from "@/components/DataBadge";
import { Notice } from "@/components/Notice";
import { getBrowserPosition } from "@/lib/format";

const PROVIDER_TONE: Record<string, "info" | "warn" | "success"> = {
  live: "success",
  cached: "info",
  disabled: "info",
  not_configured: "info",
};

type Coordinates = {
  lat: number;
  lon: number;
};

type GeocodeResponse = {
  city: string;
  display_name: string;
  latitude: number;
  longitude: number;
};

export default function PublicChargersPage() {
  const [stations, setStations] = useState<PublicStation[]>([]);
  const [provider, setProvider] = useState<ProviderMeta | null>(null);

  const [city, setCity] = useState("Noida");
  const [locationInput, setLocationInput] = useState("Noida");
  const [searchQuery, setSearchQuery] = useState("");

  const [connectorType, setConnectorType] = useState("");
  const [currentType, setCurrentType] = useState("");
  const [operationalOnly, setOperationalOnly] = useState(false);

  const [coords, setCoords] = useState<Coordinates | null>(null);
  const [radius, setRadius] = useState(25);

  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [vehicleId, setVehicleId] = useState("");
  const [compatibleOnly, setCompatibleOnly] = useState(false);

  const [isLoading, setIsLoading] = useState(true);
  const [isGeocoding, setIsGeocoding] = useState(false);
  const [error, setError] = useState("");
  const [locMessage, setLocMessage] = useState("");
  const [locationLabel, setLocationLabel] = useState("Noida");

  useEffect(() => {
    if (getToken()) {
      apiRequest<Vehicle[]>("/users/vehicles")
        .then(setVehicles)
        .catch(() => setVehicles([]));
    }
  }, []);

  const fetchStations = async () => {
    setIsLoading(true);
    setError("");

    try {
      const params = new URLSearchParams();

      if (coords) {
        params.append("latitude", String(coords.lat));
        params.append("longitude", String(coords.lon));
        params.append("radius_km", String(radius));
      } else if (city) {
        params.append("city", city);
      }

      if (searchQuery.trim()) params.append("query", searchQuery.trim());
      if (connectorType) params.append("connector_type", connectorType);
      if (currentType) params.append("current_type", currentType);
      if (operationalOnly) params.append("operational_only", "true");
      if (vehicleId) params.append("vehicle_id", vehicleId);
      if (vehicleId && compatibleOnly) {
        params.append("compatible_only", "true");
      }

      const data = await apiRequest<{
        stations: PublicStation[];
        provider: ProviderMeta;
      }>(`/discovery/search?${params.toString()}`);

      setStations(data.stations);
      setProvider(data.provider);
    } catch (err: any) {
      setStations([]);
      setError(err.message || "Could not load charging stations.");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchStations();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    city,
    connectorType,
    currentType,
    operationalOnly,
    coords,
    radius,
    vehicleId,
    compatibleOnly,
  ]);

  const searchLocation = async (event: React.FormEvent) => {
    event.preventDefault();

    const requestedLocation = locationInput.trim();

    if (requestedLocation.length < 2) {
      setLocMessage("Enter a city or locality name.");
      return;
    }

    setIsGeocoding(true);
    setLocMessage("");
    setError("");

    try {
      const result = await apiRequest<GeocodeResponse>(
        `/discovery/geocode?city=${encodeURIComponent(requestedLocation)}`
      );

      setCity(result.city || requestedLocation);
      setLocationLabel(result.display_name || requestedLocation);
      setCoords({
        lat: result.latitude,
        lon: result.longitude,
      });
    } catch (err: any) {
      setLocMessage(
        err.message || `Could not find "${requestedLocation}". Try another location.`
      );
    } finally {
      setIsGeocoding(false);
    }
  };

  const useMyLocation = async () => {
    setLocMessage("");

    try {
      const position = await getBrowserPosition();

      setCoords({
        lat: position.lat,
        lon: position.lon,
      });

      setLocationLabel("Your current location");
    } catch (e: any) {
      setLocMessage(e.message || "Could not access your location.");
    }
  };

  const useCitySearch = () => {
    setCoords(null);
    setLocationLabel(city);
    setLocationInput(city);
    setLocMessage("");
  };

  const field =
    "px-3 py-1.5 bg-slate-50 border border-slate-200 rounded-lg text-slate-700 font-medium focus:ring-1 focus:ring-brand-500";

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="mb-8 flex flex-col sm:flex-row sm:items-end justify-between gap-3">
        <div>
          <h1 className="text-3xl font-extrabold text-slate-900 tracking-tight flex items-center gap-2.5">
            <Zap className="w-7 h-7 text-brand-600 fill-current" aria-hidden="true" />
            Public EV Charging Stations
          </h1>
          <p className="text-sm text-slate-600 mt-1">
            Find public chargers across India. Each result says where its data came from; prices that are not known are shown as unavailable.
          </p>
        </div>

        <Link
          href="/compare"
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-brand-700 bg-brand-50 hover:bg-brand-100 px-3.5 py-2 rounded-lg"
          >
          <Scale className="w-4 h-4" aria-hidden="true" />
          <span>Compare prices</span>
        </Link>
      </div>

      <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm mb-6 space-y-4">
        <form
          onSubmit={searchLocation}
          className="flex flex-col sm:flex-row gap-3"
          role="search"
        >
          <div className="flex-1 flex items-center gap-2 px-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-xl">
            <MapPin className="w-5 h-5 text-slate-400 shrink-0" aria-hidden="true" />
            <label htmlFor="location-q" className="sr-only">
              Search city or locality
            </label>
            <input
              id="location-q"
              type="text"
              value={locationInput}
              onChange={(e) => setLocationInput(e.target.value)}
              maxLength={100}
              placeholder="Enter any Indian city or locality..."
              className="w-full bg-transparent text-sm focus:outline-none"
            />
          </div>

          <button
            type="button"
            onClick={useMyLocation}
            className="inline-flex items-center justify-center gap-1.5 px-4 py-2.5 bg-slate-100 hover:bg-slate-200 text-slate-700 font-semibold text-sm rounded-xl"
          >
            <LocateFixed className="w-4 h-4" aria-hidden="true" />
            Near me
          </button>

          <button
            type="submit"
            disabled={isGeocoding}
            className="px-6 py-2.5 bg-brand-600 hover:bg-brand-700 disabled:opacity-60 text-white font-semibold text-sm rounded-xl shadow-sm transition-colors"
          >
            {isGeocoding ? "Finding location..." : "Search"}
          </button>
        </form>

        {locMessage && <Notice tone="warn">{locMessage}</Notice>}

        {locationLabel && (
          <p className="text-xs text-slate-500">
            Searching around: <span className="font-semibold">{locationLabel}</span>
          </p>
        )}

        <div className="flex flex-wrap items-center gap-3 pt-2 border-t border-slate-100 text-xs">
          <span className="font-semibold text-slate-500 uppercase tracking-wider">
            Filters:
          </span>

          {coords ? (
            <>
              <label className="text-slate-600 font-medium">
                Radius
                <select
                  value={radius}
                  onChange={(e) => setRadius(Number(e.target.value))}
                  className={`ml-1.5 ${field}`}
                >
                  {[5, 10, 25, 50, 100].map((r) => (
                    <option key={r} value={r}>
                      {r} km
                    </option>
                  ))}
                </select>
              </label>

              <button
                type="button"
                onClick={useCitySearch}
                className="text-brand-700 font-semibold underline"
              >
                Use city instead
              </button>
            </>
          ) : (
            <span className="text-slate-600 font-medium">
              City search: {city}
            </span>
          )}

          <label className="sr-only" htmlFor="f-conn">
            Connector
          </label>
          <select
            id="f-conn"
            value={connectorType}
            onChange={(e) => setConnectorType(e.target.value)}
            className={field}
          >
            <option value="">All Connectors</option>
            <option value="CCS2">CCS2 (DC Fast)</option>
            <option value="Type 2">Type 2 (AC)</option>
            <option value="GB/T">GB/T</option>
            <option value="CHAdeMO">CHAdeMO</option>
          </select>

          <label className="sr-only" htmlFor="f-cur">
            Power type
          </label>
          <select
            id="f-cur"
            value={currentType}
            onChange={(e) => setCurrentType(e.target.value)}
            className={field}
          >
            <option value="">All Power Types</option>
            <option value="DC">DC Fast Only</option>
            <option value="AC">AC Standard Only</option>
          </select>

          {vehicles.length > 0 && (
            <>
              <label className="sr-only" htmlFor="f-veh">
                Vehicle
              </label>
              <select
                id="f-veh"
                value={vehicleId}
                onChange={(e) => setVehicleId(e.target.value)}
                className={field}
              >
                <option value="">No saved vehicle</option>
                {vehicles.map((v) => (
                  <option key={v.id} value={v.id}>
                    {v.make} {v.model}
                  </option>
                ))}
              </select>

              {vehicleId && (
                <label className="flex items-center gap-1.5 text-slate-700 font-medium">
                  <input
                    type="checkbox"
                    checked={compatibleOnly}
                    onChange={(e) => setCompatibleOnly(e.target.checked)}
                  />
                  Hide incompatible
                </label>
              )}
            </>
          )}

          <label className="flex items-center gap-1.5 cursor-pointer ml-auto text-slate-700 font-medium">
            <input
              type="checkbox"
              checked={operationalOnly}
              onChange={(e) => setOperationalOnly(e.target.checked)}
              className="rounded text-brand-600 focus:ring-brand-500"
            />
            Hide reported-unavailable
          </label>
        </div>
      </div>

      {provider && (
        <Notice
          tone={PROVIDER_TONE[provider.status] || "warn"}
          className="mb-6"
          title={`Data source: ${provider.provider} — ${provider.status.replace("_", " ")}`}
        >
          {provider.message}
          {provider.radius_limited && (
            <span> Live provider search is limited to {provider.radius_km_used} km.</span>
          )}
        </Notice>
      )}

      {error && (
        <Notice tone="error" className="mb-6" title="We could not load stations">
          {error}{" "}
          <button onClick={fetchStations} className="underline font-semibold ml-1">
            Try again
          </button>
        </Notice>
      )}

      {isLoading ? (
        <div
          className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6"
          aria-busy="true"
          aria-label="Loading stations"
        >
          {[0, 1, 2].map((i) => (
            <div key={i} className="h-52 rounded-2xl bg-slate-100 animate-pulse" />
          ))}
        </div>
      ) : stations.length === 0 && !error ? (
        <div className="bg-white p-12 text-center rounded-2xl border border-slate-200">
          <p className="text-slate-600 font-medium">
            No stations found matching your criteria.
          </p>
          <p className="text-xs text-slate-400 mt-1">
            Try a larger radius, another location, or fewer filters.
          </p>
          <button
            onClick={() => {
              setSearchQuery("");
              setConnectorType("");
              setCurrentType("");
              setOperationalOnly(false);
              setCompatibleOnly(false);
            }}
            className="mt-4 px-4 py-2 text-xs font-semibold text-brand-600 bg-brand-50 rounded-lg hover:bg-brand-100"
          >
            Reset Filters
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {stations.map((station) => (
            <div
              key={station.id}
              className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm hover:shadow-md transition-shadow flex flex-col justify-between"
            >
              <div>
                <div className="flex items-start justify-between gap-2 mb-2">
                  <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">
                    {station.operator_name}
                  </span>
                  <StatusBadge
                    status={station.current_status || ""}
                    confidence={station.confidence_score}
                    isSample={false}
                  />
                </div>

                <h3 className="text-base font-bold text-slate-900 leading-snug mb-1">
                  {station.name}
                </h3>

                <p className="text-xs text-slate-500 mb-2 flex items-center gap-1">
                  <MapPin
                    className="w-3.5 h-3.5 text-slate-400 shrink-0"
                    aria-hidden="true"
                  />
                  {station.address}, {station.city}
                  {station.distance_km != null && (
                    <span className="ml-1 text-slate-400">
                      · {station.distance_km} km straight-line
                    </span>
                  )}
                </p>

                <div className="mb-3">
                  <DataBadge
                    origin={station.data_origin}
                    syncedAt={station.last_synced_at}
                  />
                </div>

                <div className="flex flex-wrap gap-1.5 mb-3">
                  {station.connectors_summary.map((conn, idx) => (
                    <span
                      key={idx}
                      className="px-2 py-0.5 rounded text-[11px] font-semibold bg-emerald-50 text-emerald-800 border border-emerald-100"
                    >
                      {conn}
                    </span>
                  ))}
                </div>

                {station.compatibility && (
                  <p
                    className={`text-[11px] font-semibold mb-2 ${
                      station.compatibility.status === "compatible"
                        ? "text-emerald-700"
                        : station.compatibility.status === "incompatible"
                          ? "text-rose-700"
                          : "text-amber-700"
                    }`}
                  >
                    {station.compatibility.status === "compatible"
                      ? "Compatible with your vehicle"
                      : station.compatibility.status === "incompatible"
                        ? "Not compatible: "
                        : "Compatibility unconfirmed: "}
                    {station.compatibility.status !== "compatible" &&
                      station.compatibility.reasons[0]}
                  </p>
                )}
              </div>

              <div className="pt-4 border-t border-slate-100 flex items-center justify-between">
                <div>
                  <span className="text-[10px] text-slate-400 uppercase font-semibold block">
                    Price
                  </span>
                  <span
                    className={`text-xs font-semibold ${
                      station.price_status === "known"
                        ? "text-slate-800"
                        : "text-slate-500"
                    }`}
                  >
                    {station.price_summary}
                  </span>
                </div>

                <Link
                  href={`/public-chargers/${station.id}`}
                  className="inline-flex items-center gap-1 px-3 py-1.5 text-xs font-semibold text-white bg-brand-600 hover:bg-brand-700 rounded-lg shadow-sm transition-colors"
                >
                  Details <ArrowRight className="w-3 h-3" aria-hidden="true" />
                </Link>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}