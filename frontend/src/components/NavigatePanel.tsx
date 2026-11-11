"use client";

import React, { useState } from "react";
import { Navigation, LocateFixed } from "lucide-react";
import { apiRequest } from "@/lib/api";
import { getBrowserPosition } from "@/lib/format";
import { Notice } from "@/components/Notice";
import { MapView } from "@/components/MapView";

interface Props {
  targetType: "station" | "listing";
  targetId: number;
}

/** Navigate action. Destination coordinates come from the server; home chargers get an approximate pin until booking. */
export function NavigatePanel({ targetType, targetId }: Props) {
  const [open, setOpen] = useState(false);
  const [originText, setOriginText] = useState("");
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [origin, setOrigin] = useState<{ lat: number; lon: number } | null>(null);

  const load = async (o: { lat: number; lon: number } | null, text?: string) => {
    setLoading(true);
    setError("");
    try {
      const q = new URLSearchParams({ target_type: targetType, target_id: String(targetId) });
      if (o) { q.set("origin_lat", String(o.lat)); q.set("origin_lon", String(o.lon)); }
      else if (text) q.set("origin_text", text);
      setData(await apiRequest<any>(`/navigation/route?${q.toString()}`));
    } catch (e: any) {
      setData(null);
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const useMyLocation = async () => {
    setError("");
    try {
      const pos = await getBrowserPosition();
      setOrigin(pos);
      await load(pos);
    } catch (e: any) {
      setError(e.message); // denied / unavailable: manual entry stays available
    }
  };

  const route = data?.route;
  return (
    <div className="space-y-3">
      <button onClick={() => { setOpen((v) => !v); if (!data) load(null); }} aria-expanded={open}
        className="inline-flex items-center justify-center gap-2 px-4 py-2.5 bg-brand-600 hover:bg-brand-700 text-white font-semibold text-xs rounded-xl shadow-sm transition-colors w-full">
        <Navigation className="w-4 h-4" aria-hidden="true" /> Navigate
      </button>
      {open && (
        <div className="p-4 bg-white border border-slate-200 rounded-2xl space-y-3 text-xs shadow-sm">
          <div className="flex flex-col sm:flex-row gap-2">
            <button type="button" onClick={useMyLocation} className="inline-flex items-center justify-center gap-1.5 px-3 py-2 bg-slate-100 hover:bg-slate-200 rounded-lg font-semibold text-slate-700">
              <LocateFixed className="w-3.5 h-3.5" aria-hidden="true" /> Use my current location
            </button>
            <form className="flex flex-1 gap-2" onSubmit={(e) => { e.preventDefault(); if (originText.trim()) { setOrigin(null); load(null, originText.trim()); } }}>
              <label className="sr-only" htmlFor={`origin-${targetType}-${targetId}`}>Starting location</label>
              <input id={`origin-${targetType}-${targetId}`} value={originText} onChange={(e) => setOriginText(e.target.value)} placeholder="…or type a starting point"
                maxLength={200} className="flex-1 px-3 py-2 border border-slate-300 rounded-lg" />
              <button className="px-3 py-2 bg-brand-600 text-white rounded-lg font-semibold">Set</button>
            </form>
          </div>

          {loading && <p className="text-slate-500">Preparing navigation…</p>}
          {error && <Notice tone="warn">{error}</Notice>}

          {data && (
            <>
              {data.note && <Notice tone="info">{data.note}</Notice>}
              {route?.available ? (
                <Notice tone="success" title="Route (from the routing service)">
                  {route.distance_km} km by road · about {route.duration_min} min ({route.provider}). Traffic is not guaranteed; open the map link for live conditions.
                </Notice>
              ) : (
                route?.message && <Notice tone="info">{route.message}</Notice>
              )}
              {route?.available && route.geometry && (
                <div className="h-56"><MapView center={[data.destination.latitude, data.destination.longitude]} zoom={12} route={route.geometry} className="w-full h-full rounded-xl overflow-hidden border border-slate-200" /></div>
              )}
              <div className="flex flex-wrap gap-2">
                <a href={data.links.google_maps} target="_blank" rel="noopener noreferrer" className="px-3 py-2 bg-white border border-slate-300 hover:bg-slate-50 rounded-lg font-semibold text-slate-800">Open in Google Maps</a>
                <a href={data.links.apple_maps} target="_blank" rel="noopener noreferrer" className="px-3 py-2 bg-white border border-slate-300 hover:bg-slate-50 rounded-lg font-semibold text-slate-800">Open in Apple Maps</a>
              </div>
              <p className="text-slate-400">Turn-by-turn guidance happens in the map app you open; ChargeCircle does not provide in-app turn-by-turn navigation.</p>
            </>
          )}
        </div>
      )}
    </div>
  );
}
