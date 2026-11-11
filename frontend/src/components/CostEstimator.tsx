"use client";

import React, { useEffect, useState } from "react";
import { Calculator } from "lucide-react";
import { apiRequest, getToken } from "@/lib/api";
import { Estimate, Vehicle } from "@/types";
import { inr, timeAgo } from "@/lib/format";
import { Notice } from "@/components/Notice";

interface Props {
  targetType: "station" | "listing";
  targetId: number;
  connectors?: { id: number; label: string }[];
}

/** Charging-cost estimator. Shows its working, its assumptions, and what it had to leave out. */
export function CostEstimator({ targetType, targetId, connectors = [] }: Props) {
  const [mode, setMode] = useState<"kwh" | "battery">("kwh");
  const [kwh, setKwh] = useState("20");
  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [vehicleId, setVehicleId] = useState("");
  const [fromSoc, setFromSoc] = useState("20");
  const [toSoc, setToSoc] = useState("80");
  const [connectorId, setConnectorId] = useState("");
  const [hours, setHours] = useState("");
  const [result, setResult] = useState<Estimate | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!getToken()) return;
    apiRequest<Vehicle[]>("/users/vehicles").then(setVehicles).catch(() => setVehicles([]));
  }, []);

  const run = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const body: any = { target_type: targetType, target_id: targetId };
      if (mode === "kwh") body.energy_kwh = Number(kwh);
      else {
        body.vehicle_id = Number(vehicleId);
        body.from_soc_percent = Number(fromSoc);
        body.to_soc_percent = Number(toSoc);
      }
      if (connectorId) body.connector_id = Number(connectorId);
      if (hours && targetType === "listing") body.hours = Number(hours);
      setResult(await apiRequest<Estimate>("/pricing/estimate", { method: "POST", body: JSON.stringify(body) }));
    } catch (err: any) {
      setResult(null);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const inputCls = "w-full px-3 py-2 bg-white border border-slate-300 rounded-lg text-sm focus:ring-1 focus:ring-brand-500 focus:outline-none";
  return (
    <section aria-labelledby="estimator-title" className="bg-white rounded-3xl p-6 border border-slate-200 shadow-sm space-y-4">
      <h2 id="estimator-title" className="text-lg font-bold text-slate-900 flex items-center gap-2">
        <Calculator className="w-5 h-5 text-brand-600" aria-hidden="true" /> Charging cost estimator
      </h2>
      <form onSubmit={run} className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
        <fieldset className="sm:col-span-2 flex gap-4">
          <legend className="sr-only">How should we work out the energy?</legend>
          <label className="flex items-center gap-1.5 font-medium text-slate-700">
            <input type="radio" name="mode" checked={mode === "kwh"} onChange={() => setMode("kwh")} /> I know the energy (kWh)
          </label>
          <label className={`flex items-center gap-1.5 font-medium ${vehicles.length ? "text-slate-700" : "text-slate-400"}`}>
            <input type="radio" name="mode" disabled={!vehicles.length} checked={mode === "battery"} onChange={() => setMode("battery")} />
            From my vehicle's battery {!vehicles.length && "(sign in and save a vehicle)"}
          </label>
        </fieldset>
        {mode === "kwh" ? (
          <label className="font-semibold text-slate-600">Energy needed (kWh)
            <input className={inputCls} type="number" min="0.1" max="500" step="0.1" required value={kwh} onChange={(e) => setKwh(e.target.value)} />
          </label>
        ) : (
          <>
            <label className="font-semibold text-slate-600">Vehicle
              <select className={inputCls} required value={vehicleId} onChange={(e) => setVehicleId(e.target.value)}>
                <option value="">Select…</option>
                {vehicles.map((v) => <option key={v.id} value={v.id}>{v.make} {v.model}{v.battery_capacity_kwh ? ` (${v.battery_capacity_kwh} kWh)` : " (battery unknown)"}</option>)}
              </select>
            </label>
            <label className="font-semibold text-slate-600">From % → To %
              <span className="flex gap-2">
                <input aria-label="Start charge percent" className={inputCls} type="number" min="0" max="100" value={fromSoc} onChange={(e) => setFromSoc(e.target.value)} />
                <input aria-label="Target charge percent" className={inputCls} type="number" min="0" max="100" value={toSoc} onChange={(e) => setToSoc(e.target.value)} />
              </span>
            </label>
          </>
        )}
        {connectors.length > 1 && (
          <label className="font-semibold text-slate-600">Connector
            <select className={inputCls} value={connectorId} onChange={(e) => setConnectorId(e.target.value)}>
              <option value="">Best match</option>
              {connectors.map((c) => <option key={c.id} value={c.id}>{c.label}</option>)}
            </select>
          </label>
        )}
        {targetType === "listing" && (
          <label className="font-semibold text-slate-600">Booked hours (optional)
            <input className={inputCls} type="number" min="0.5" max="24" step="0.5" value={hours} onChange={(e) => setHours(e.target.value)} />
          </label>
        )}
        <div className="sm:col-span-2">
          <button disabled={loading} className="px-5 py-2.5 bg-brand-600 hover:bg-brand-700 disabled:opacity-60 text-white font-semibold rounded-xl text-xs">
            {loading ? "Calculating…" : "Estimate cost"}
          </button>
        </div>
      </form>

      {error && <Notice tone="error">{error}</Notice>}

      {result && (
        <div className="space-y-3 text-xs" aria-live="polite">
          <table className="w-full">
            <caption className="sr-only">Cost breakdown</caption>
            <tbody>
              {result.lines.map((l) => (
                <tr key={l.label} className="border-b border-slate-100">
                  <th scope="row" className="text-left py-1.5 font-medium text-slate-700">{l.label}<span className="block font-normal text-slate-400">{l.basis}</span></th>
                  <td className="text-right font-semibold text-slate-900">{l.amount === null ? "Unknown" : inr(l.amount)}</td>
                </tr>
              ))}
              <tr>
                <th scope="row" className="text-left py-2 font-bold text-slate-900">{result.is_complete ? "Estimated total" : "Known charges only (excludes the unknown items below)"}</th>
                <td className="text-right font-extrabold text-slate-900 text-base">{inr(result.total_known)}</td>
              </tr>
            </tbody>
          </table>
          {result.excluded.length > 0 && (
            <Notice tone="warn" title="Not included in this estimate">
              <ul className="list-disc ml-4">{result.excluded.map((x) => <li key={x}>{x}</li>)}</ul>
            </Notice>
          )}
          <Notice tone="info" title="Assumptions">
            <ul className="list-disc ml-4">{result.assumptions.map((x) => <li key={x}>{x}</li>)}</ul>
            {result.price_source_label && (
              <p className="mt-1">Price source: {result.price_source_label}{result.price_updated_at ? `, updated ${timeAgo(result.price_updated_at)}` : ""}. {result.price_verified ? "Verified." : "Not verified."}</p>
            )}
          </Notice>
        </div>
      )}
    </section>
  );
}
