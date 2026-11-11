"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { Scale, LocateFixed, Home, Zap } from "lucide-react";
import { apiRequest, getToken } from "@/lib/api";
import { Vehicle } from "@/types";
import { inr, getBrowserPosition, timeAgo } from "@/lib/format";
import { Notice } from "@/components/Notice";
import { DataBadge } from "@/components/DataBadge";

const CITIES: Record<string, [number, number]> = {
  Bengaluru: [12.9716, 77.5946], Mumbai: [19.076, 72.8777], Gurugram: [28.4595, 77.0266], Delhi: [28.6139, 77.209],
};

export default function ComparePage() {
  const [city, setCity] = useState("Bengaluru");
  const [coords, setCoords] = useState<{ lat: number; lon: number } | null>(null);
  const [radius, setRadius] = useState(15);
  const [mode, setMode] = useState<"kwh" | "battery">("kwh");
  const [kwh, setKwh] = useState("20");
  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [vehicleId, setVehicleId] = useState("");
  const [fromSoc, setFromSoc] = useState("20");
  const [toSoc, setToSoc] = useState("80");
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [locMessage, setLocMessage] = useState("");

  useEffect(() => {
    if (getToken()) apiRequest<Vehicle[]>("/users/vehicles").then(setVehicles).catch(() => setVehicles([]));
  }, []);

  const run = async (e?: React.FormEvent) => {
    e?.preventDefault();
    setLoading(true);
    setError("");
    try {
      const [lat, lon] = coords ? [coords.lat, coords.lon] : CITIES[city];
      const q = new URLSearchParams({ latitude: String(lat), longitude: String(lon), radius_km: String(radius) });
      if (mode === "kwh") q.set("energy_kwh", kwh);
      else { q.set("vehicle_id", vehicleId); q.set("from_soc_percent", fromSoc); q.set("to_soc_percent", toSoc); }
      if (mode === "kwh" && vehicleId) q.set("vehicle_id", vehicleId);
      setData(await apiRequest<any>(`/compare?${q.toString()}`));
    } catch (err: any) {
      setData(null);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const nearMe = async () => {
    setLocMessage("");
    try { setCoords(await getBrowserPosition()); } catch (e: any) { setLocMessage(e.message); }
  };

  const inp = "px-3 py-2 bg-white border border-slate-300 rounded-lg text-sm focus:ring-1 focus:ring-brand-500 focus:outline-none";
  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      <div>
        <h1 className="text-3xl font-extrabold text-slate-900 tracking-tight flex items-center gap-2.5">
          <Scale className="w-7 h-7 text-brand-600" aria-hidden="true" /> Compare charging options
        </h1>
        <p className="text-sm text-slate-600 mt-1">Public stations and home chargers side by side for the same energy need, in ₹. Unknown prices are never guessed.</p>
      </div>

      <form onSubmit={run} className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs items-end">
        <label className="font-semibold text-slate-600">{coords ? "Using your location" : "City"}
          <select className={`${inp} w-full`} value={city} disabled={!!coords} onChange={(e) => setCity(e.target.value)}>
            {Object.keys(CITIES).map((c) => <option key={c}>{c}</option>)}
          </select>
        </label>
        <div className="flex gap-2">
          <button type="button" onClick={coords ? () => setCoords(null) : nearMe} className="inline-flex items-center gap-1.5 px-3 py-2 bg-slate-100 hover:bg-slate-200 rounded-lg font-semibold text-slate-700">
            <LocateFixed className="w-3.5 h-3.5" aria-hidden="true" /> {coords ? "Use city instead" : "Near me"}
          </button>
          <label className="font-semibold text-slate-600 flex-1">Radius
            <select className={`${inp} w-full`} value={radius} onChange={(e) => setRadius(Number(e.target.value))}>{[5, 10, 15, 30, 50].map((r) => <option key={r} value={r}>{r} km</option>)}</select>
          </label>
        </div>
        <fieldset className="flex gap-3">
          <legend className="sr-only">Energy input</legend>
          <label className="flex items-center gap-1 font-medium text-slate-700"><input type="radio" checked={mode === "kwh"} onChange={() => setMode("kwh")} /> kWh</label>
          <label className={`flex items-center gap-1 font-medium ${vehicles.length ? "text-slate-700" : "text-slate-400"}`}><input type="radio" disabled={!vehicles.length} checked={mode === "battery"} onChange={() => setMode("battery")} /> Battery %</label>
        </fieldset>
        {mode === "kwh" ? (
          <label className="font-semibold text-slate-600">Energy needed (kWh)
            <input className={`${inp} w-full`} type="number" min="0.1" max="500" step="0.1" required value={kwh} onChange={(e) => setKwh(e.target.value)} />
          </label>
        ) : (
          <label className="font-semibold text-slate-600 sm:col-span-1">From % → To %
            <span className="flex gap-2"><input aria-label="From percent" className={`${inp} w-full`} type="number" min="0" max="100" value={fromSoc} onChange={(e) => setFromSoc(e.target.value)} />
              <input aria-label="To percent" className={`${inp} w-full`} type="number" min="0" max="100" value={toSoc} onChange={(e) => setToSoc(e.target.value)} /></span>
          </label>
        )}
        {vehicles.length > 0 && (
          <label className="font-semibold text-slate-600">Vehicle (for compatibility{mode === "battery" ? " and battery" : ""})
            <select className={`${inp} w-full`} value={vehicleId} required={mode === "battery"} onChange={(e) => setVehicleId(e.target.value)}>
              <option value="">None</option>{vehicles.map((v) => <option key={v.id} value={v.id}>{v.make} {v.model}</option>)}
            </select>
          </label>
        )}
        <button disabled={loading} className="px-5 py-2.5 bg-brand-600 hover:bg-brand-700 disabled:opacity-60 text-white font-semibold rounded-xl">{loading ? "Comparing…" : "Compare"}</button>
      </form>
      {locMessage && <Notice tone="warn">{locMessage}</Notice>}
      {error && <Notice tone="error">{error}</Notice>}

      {data && (
        <div className="space-y-4" aria-live="polite">
          <Notice tone="info">
            Comparing for {data.energy_kwh} kWh. {data.energy_note} {data.routing.message} {data.note}
          </Notice>
          {data.provider && data.provider.status !== "disabled" && data.provider.status !== "not_configured" && <Notice tone={data.provider.status === "live" || data.provider.status === "cached" ? "success" : "warn"}>{data.provider.message}</Notice>}
          {data.candidates.length === 0 && <div className="bg-white p-10 text-center rounded-2xl border border-slate-200 text-slate-600">No chargers found in this area. Try a larger radius.</div>}
          <div className="overflow-x-auto bg-white rounded-2xl border border-slate-200">
            <table className="w-full text-xs min-w-[860px]">
              <caption className="sr-only">Charging options ranked by estimated cost</caption>
              <thead className="bg-slate-50 text-slate-500 uppercase text-[10px] tracking-wider">
                <tr>{["Option", "Estimated cost", "Distance", "Connector & power", "Compatibility", "Access & data"].map((h) => <th key={h} scope="col" className="text-left px-3 py-2.5">{h}</th>)}</tr>
              </thead>
              <tbody>
                {data.candidates.map((c: any) => (
                  <tr key={`${c.kind}-${c.id}`} className="border-t border-slate-100 align-top">
                    <td className="px-3 py-3 max-w-[220px]">
                      <Link href={c.link} className="font-bold text-slate-900 hover:text-brand-700 inline-flex items-center gap-1.5">
                        {c.kind === "home" ? <Home className="w-3.5 h-3.5 text-blue-600" aria-label="Home charger" /> : <Zap className="w-3.5 h-3.5 text-emerald-600" aria-label="Public station" />}{c.name}
                      </Link>
                      <span className="block text-slate-500">{c.operator} · {c.address}</span>
                      {c.is_lowest_estimated_total && <span className="inline-block mt-1 px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 font-bold">Lowest estimated total</span>}
                    </td>
                    <td className="px-3 py-3">
                      <span className="text-sm font-extrabold text-slate-900">{c.estimate.price_confidence === "unknown" ? "Price unavailable" : inr(c.estimate.total_known)}</span>
                      <span className="block text-slate-500">{c.price_label}</span>
                      {c.estimate.excluded.length > 0 && <span className="block text-amber-700">Excludes: {c.estimate.excluded.slice(0, 3).join("; ")}</span>}
                      <details className="mt-1"><summary className="cursor-pointer text-brand-700 font-semibold">How this is calculated</summary>
                        <ul className="mt-1 space-y-0.5">{c.estimate.lines.map((l: any) => <li key={l.label}>{l.label}: {l.amount === null ? "unknown" : inr(l.amount)} <span className="text-slate-400">({l.basis})</span></li>)}</ul>
                        <ul className="mt-1 list-disc ml-4 text-slate-500">{c.estimate.assumptions.map((a: string) => <li key={a}>{a}</li>)}</ul>
                      </details>
                      {c.booking_conditions && <span className="block text-slate-500 mt-1">Min. {c.booking_conditions.minimum_hours} h · {c.booking_conditions.cancellation_policy || "see listing"}</span>}
                    </td>
                    <td className="px-3 py-3">
                      {c.distance_straight_km} km <span className="text-slate-400">straight-line</span>
                      {c.road_distance_km != null ? <span className="block">{c.road_distance_km} km by road · ~{c.travel_minutes} min</span> : <span className="block text-slate-400">Road distance unavailable</span>}
                      {c.is_approximate_location && <span className="block text-slate-400">Approximate area</span>}
                    </td>
                    <td className="px-3 py-3">{c.connector}{c.effective_power_kw ? <span className="block text-slate-500">Effective ≈ {c.effective_power_kw} kW for you</span> : c.rated_power_kw ? <span className="block text-slate-500">Up to {c.rated_power_kw} kW</span> : <span className="block text-slate-400">Power not stated</span>}</td>
                    <td className="px-3 py-3">{c.compatibility ? <span className={c.compatibility.status === "compatible" ? "text-emerald-700 font-semibold" : c.compatibility.status === "incompatible" ? "text-rose-700 font-semibold" : "text-amber-700 font-semibold"}>{c.compatibility.status}<span className="block font-normal text-slate-500">{c.compatibility.reasons[0]}</span></span> : <span className="text-slate-400">Select a vehicle to check</span>}</td>
                    <td className="px-3 py-3">
                      <span className="block">{c.access_type}{c.access_note ? ` · ${c.access_note}` : ""}</span>
                      <span className="block text-slate-500">{c.availability.status}{c.availability.confidence != null ? ` (${Math.round(c.availability.confidence * 100)}% confidence)` : ""}</span>
                      <span className="block text-slate-400">{c.availability.note}</span>
                      <span className="block mt-1">{c.kind === "station" ? <DataBadge origin={c.data_origin} syncedAt={c.data_freshness.station_synced_at} /> : <span className="text-slate-500">Host-set price{c.data_freshness.price_updated_at ? `, updated ${timeAgo(c.data_freshness.price_updated_at)}` : ""}</span>}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
