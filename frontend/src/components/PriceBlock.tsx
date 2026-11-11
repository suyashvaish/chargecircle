import React from "react";
import { BadgeCheck } from "lucide-react";
import { inr, timeAgo } from "@/lib/format";

/** Public price display for a connector. Unknown values are labelled, never filled in. */
export function PriceBlock({ conn }: { conn: any }) {
  const rows: [string, string][] = [];
  if (conn.session_fee !== null && conn.session_fee !== undefined) rows.push(["Session fee", inr(conn.session_fee)]);
  if (conn.time_fee_per_min !== null && conn.time_fee_per_min !== undefined) rows.push(["Time fee", `${inr(conn.time_fee_per_min)}/min`]);
  if (conn.idle_fee_per_min !== null && conn.idle_fee_per_min !== undefined) rows.push(["Idle fee", `${inr(conn.idle_fee_per_min)}/min`]);
  const taxes = conn.taxes_included === true ? "Taxes included" : conn.taxes_included === false ? "Taxes extra" : "Taxes: not stated";
  return (
    <div className="text-right">
      {conn.pricing_per_kwh !== null && conn.pricing_per_kwh !== undefined ? (
        <>
          <span className="text-base font-extrabold text-slate-900">{inr(conn.pricing_per_kwh)}</span>
          <span className="text-[11px] text-slate-400 block">per kWh (energy)</span>
        </>
      ) : (
        <span className="text-sm font-bold text-slate-500">Price unavailable</span>
      )}
      {rows.map(([k, v]) => (
        <span key={k} className="text-[11px] text-slate-500 block">{k}: {v}</span>
      ))}
      {conn.pricing_per_kwh !== null && conn.pricing_per_kwh !== undefined && <span className="text-[11px] text-slate-400 block">{taxes}</span>}
      {conn.price_source && (
        <span className="text-[11px] text-slate-500 block mt-0.5">
          {conn.price_verified && <BadgeCheck className="inline w-3 h-3 text-emerald-600 mr-0.5" aria-label="verified" />}
          {conn.price_verified ? "Verified · " : "Not verified · "}
          {conn.price_source_label}
          {conn.price_updated_at ? ` · updated ${timeAgo(conn.price_updated_at)}` : ""}
        </span>
      )}
    </div>
  );
}
