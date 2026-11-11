"use client";

import React, { useEffect, useRef } from "react";
import { PublicStation, HomeListing } from "@/types";
import { escapeHtml } from "@/lib/format";
import "leaflet/dist/leaflet.css";

interface MapViewProps {
  publicStations?: PublicStation[];
  homeListings?: HomeListing[];
  center?: [number, number];
  zoom?: number;
  route?: [number, number][];
  onSelectStation?: (station: PublicStation) => void;
  onSelectListing?: (listing: HomeListing) => void;
  className?: string;
}

/**
 * Map of stations and home chargers. Every string that reaches popup HTML is escaped (host-written titles
 * must never be able to inject markup). Home chargers are drawn as an approximate-area circle, not a precise pin.
 */
export function MapView({
  publicStations = [],
  homeListings = [],
  center = [12.9716, 77.5946],
  zoom = 12,
  route,
  onSelectStation,
  onSelectListing,
  className = "w-full h-full min-h-[400px] rounded-2xl overflow-hidden shadow-inner border border-slate-200",
}: MapViewProps) {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<any>(null);

  useEffect(() => {
    if (!mapContainerRef.current) return;
    let isMounted = true;

    import("leaflet").then((L) => {
      if (!isMounted || !mapContainerRef.current) return;

      if (!mapInstanceRef.current) {
        const map = L.map(mapContainerRef.current).setView(center, zoom);
        mapInstanceRef.current = map;
        L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
          attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
          maxZoom: 19,
        }).addTo(map);
      } else {
        mapInstanceRef.current.setView(center, zoom);
      }
      const map = mapInstanceRef.current;

      map.eachLayer((layer: any) => {
        if (layer instanceof L.Marker || layer instanceof L.Circle || layer instanceof L.Polyline) map.removeLayer(layer);
      });

      const createIcon = (color: string, label: string) =>
        L.divIcon({
          className: "custom-div-icon",
          html: `<div style="background-color:${color};width:34px;height:34px;border-radius:50%;display:flex;align-items:center;justify-content:center;color:white;font-weight:bold;font-size:11px;box-shadow:0 4px 6px rgba(0,0,0,0.3);border:2px solid white;">${label}</div>`,
          iconSize: [34, 34], iconAnchor: [17, 34], popupAnchor: [0, -34],
        });
      const publicIcon = createIcon("#059669", "⚡");
      const homeIcon = createIcon("#2563eb", "🏠");

      publicStations.forEach((station) => {
        if (!station.latitude || !station.longitude) return;
        const marker = L.marker([station.latitude, station.longitude], { icon: publicIcon }).addTo(map);
        const chips = (station.connectors_summary || []).map((c) => `<span style="background:#ecfdf5;color:#047857;font-size:10px;padding:2px 6px;border-radius:4px;font-weight:600;">${escapeHtml(c)}</span>`).join("");
        marker.bindPopup(`
          <div style="font-size:13px;line-height:1.4;padding:2px;">
            <strong style="color:#0f172a;font-size:14px;display:block;margin-bottom:4px;">${escapeHtml(station.name)}</strong>
            <div style="color:#64748b;font-size:12px;margin-bottom:6px;">${escapeHtml(station.locality || station.city)} • ${escapeHtml(station.operator_name)}</div>
            <div style="display:flex;gap:4px;flex-wrap:wrap;margin-bottom:6px;">${chips}</div>
            <div style="font-size:11px;color:#334155;font-weight:600;margin-bottom:2px;">${escapeHtml(station.price_summary)}</div>
            <div style="font-size:11px;color:#64748b;margin-bottom:8px;">${station.data_origin === "sample" ? "Sample data" : station.data_origin === "provider" ? "Open Charge Map data" : "Manually entered"}</div>
            <a href="/public-chargers/${Number(station.id)}" style="display:block;text-align:center;background:#059669;color:white;text-decoration:none;padding:6px 12px;border-radius:6px;font-weight:500;font-size:12px;">View station</a>
          </div>`);
        marker.on("click", () => onSelectStation && onSelectStation(station));
      });

      homeListings.forEach((listing) => {
        if (!listing.latitude || !listing.longitude) return;
        const pos: [number, number] = [listing.latitude, listing.longitude];
        if (listing.location_is_approximate) {
          L.circle(pos, { radius: 400, color: "#2563eb", weight: 1, fillOpacity: 0.12 }).addTo(map);
        }
        const marker = L.marker(pos, { icon: homeIcon }).addTo(map);
        marker.bindPopup(`
          <div style="font-size:13px;line-height:1.4;padding:2px;">
            <strong style="color:#0f172a;font-size:14px;display:block;margin-bottom:4px;">${escapeHtml(listing.title)}</strong>
            <div style="color:#64748b;font-size:12px;margin-bottom:6px;">${escapeHtml(listing.display_address)}${listing.location_is_approximate ? " (approximate area)" : ""}</div>
            <div style="display:flex;gap:4px;margin-bottom:6px;">
              <span style="background:#eff6ff;color:#1d4ed8;font-size:10px;padding:2px 6px;border-radius:4px;font-weight:600;">${escapeHtml(listing.connector_type)} • ${Number(listing.power_kw)} kW</span>
              <span style="background:#f1f5f9;color:#334155;font-size:10px;padding:2px 6px;border-radius:4px;font-weight:600;">₹${Number(listing.price_per_kwh)}/kWh</span>
            </div>
            <a href="/marketplace/${Number(listing.id)}" style="display:block;text-align:center;background:#2563eb;color:white;text-decoration:none;padding:6px 12px;border-radius:6px;font-weight:500;font-size:12px;">View home charger</a>
          </div>`);
        marker.on("click", () => onSelectListing && onSelectListing(listing));
      });

      if (route && route.length > 1) {
        const line = L.polyline(route, { color: "#059669", weight: 4 }).addTo(map);
        map.fitBounds(line.getBounds(), { padding: [20, 20] });
      }
    });

    return () => { isMounted = false; };
  }, [publicStations, homeListings, center, zoom, route, onSelectStation, onSelectListing]);

  // Release the Leaflet instance when the component unmounts.
  useEffect(() => () => {
    if (mapInstanceRef.current) { mapInstanceRef.current.remove(); mapInstanceRef.current = null; }
  }, []);

  return <div ref={mapContainerRef} className={className} role="region" aria-label="Map of charging locations" />;
}
