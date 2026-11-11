"use client";

import React, { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  Zap,
  MapPin,
  Clock,
  DollarSign,
  Navigation,
  ShieldCheck,
  AlertTriangle,
  ArrowLeft,
  CheckCircle,
  Database,
} from "lucide-react";
import { apiRequest } from "@/lib/api";
import { PublicStation, ReliabilityScore } from "@/types";
import { StatusBadge } from "@/components/StatusBadge";
import { ReportModal } from "@/components/ReportModal";
import { DataBadge } from "@/components/DataBadge";
import { PriceBlock } from "@/components/PriceBlock";
import { CostEstimator } from "@/components/CostEstimator";
import { NavigatePanel } from "@/components/NavigatePanel";
import { Notice } from "@/components/Notice";
import { inr } from "@/lib/format";

export default function StationDetailPage() {
  const params = useParams();
  const router = useRouter();
  const stationId = Number(params?.id);

  const [station, setStation] = useState<any>(null);
  const [reliability, setReliability] = useState<ReliabilityScore | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [reportModalOpen, setReportModalOpen] = useState(false);

  const loadStation = async () => {
    if (!stationId) return;
    try {
      const [stationData, relData] = await Promise.all([
        apiRequest<any>(`/discovery/stations/${stationId}`),
        apiRequest<ReliabilityScore>(`/reliability/status/station/${stationId}`).catch(() => null),
      ]);
      setStation(stationData);
      setReliability(relData);
    } catch (err: any) {
      if (err.status !== 404) setLoadError(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadStation();
  }, [stationId]);

  if (isLoading) {
    return <div className="py-24 text-center text-slate-400">Loading charging station details...</div>;
  }

  if (!station) {
    return (
      <div className="max-w-xl mx-auto py-24 px-4 text-center">
        <h2 className="text-xl font-bold text-slate-900">Station Not Found</h2>
        <p className="text-sm text-slate-500 mt-2">The requested public station could not be found.</p>
        {loadError && <div className="mt-3 text-left"><Notice tone="error">{loadError}</Notice></div>}
        <Link href="/public-chargers" className="mt-4 inline-block text-brand-600 font-semibold text-sm">
          &larr; Return to Public Discovery
        </Link>
      </div>
    );
  }

  const connectorOptions = (station.points || []).flatMap((pt: any) =>
    (pt.connectors || []).map((c: any) => ({ id: c.id, label: `${c.connector_type}${c.power_kw ? ` ${c.power_kw} kW` : ""} ${c.current_type}` })));

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      {/* Back Button */}
      <Link
        href="/public-chargers"
        className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-500 hover:text-slate-900 transition-colors"
      >
        <ArrowLeft className="w-4 h-4" />
        Back to Public Stations
      </Link>

      {/* Header Card */}
      <div className="bg-white rounded-3xl p-6 sm:p-8 border border-slate-200 shadow-sm space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-2">
              <span className="text-xs font-bold text-brand-700 bg-brand-50 border border-brand-200 px-2.5 py-0.5 rounded-full uppercase tracking-wider">
                {station.operator_name}
              </span>
              <StatusBadge status={station.current_status || ""} confidence={station.confidence_score} isSample={false} />
              <DataBadge origin={station.data_origin} syncedAt={station.last_synced_at} />
            </div>
            <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight">
              {station.name}
            </h1>
            <p className="text-sm text-slate-500 mt-1 flex items-center gap-1.5">
              <MapPin className="w-4 h-4 text-slate-400 shrink-0" />
              {station.address}, {station.locality}, {station.city} - {station.pin_code}
            </p>
          </div>

          <div className="flex flex-wrap sm:flex-col gap-2 shrink-0">
            <NavigatePanel targetType="station" targetId={station.id} />
            <button
              onClick={() => setReportModalOpen(true)}
              className="inline-flex items-center justify-center gap-1.5 px-4 py-2.5 bg-slate-100 hover:bg-slate-200 text-slate-700 font-semibold text-xs rounded-xl transition-colors"
            >
              <AlertTriangle className="w-3.5 h-3.5 text-orange-600" />
              Report Issue
            </button>
          </div>
        </div>

        {/* Operational Reliability Card */}
        <div className="p-4 rounded-2xl bg-slate-50 border border-slate-200 flex flex-col sm:flex-row sm:items-center justify-between gap-4 text-xs">
          <div>
            <div className="font-semibold text-slate-800 flex items-center gap-1.5">
              <ShieldCheck className="w-4 h-4 text-brand-600" />
              Operational Reliability Breakdown
            </div>
            <p className="text-slate-500 mt-0.5">
              {reliability?.evidence_summary || "Calculated using exponential time-decay half-life of 72 hours."}
            </p>
          </div>
          <div className="flex gap-4 shrink-0 text-right">
            <div>
              <span className="text-slate-400 block text-[10px] uppercase font-bold">Confidence</span>
              <span className="font-bold text-slate-900 text-sm">
                {reliability ? `${Math.round(reliability.confidence_score * 100)}%` : "N/A"}
              </span>
            </div>
            <div>
              <span className="text-slate-400 block text-[10px] uppercase font-bold">Reports</span>
              <span className="font-bold text-slate-900 text-sm">
                {reliability?.total_reports_evaluated || 0}
              </span>
            </div>
          </div>
        </div>
      </div>

      {station.is_sample && (
        <Notice tone="warn" title="Sample data">This station comes from the sample dataset. Its location and any price are illustrative, not a real, current tariff.</Notice>
      )}
      {station.provider_status && station.data_origin === "provider" && (
        <Notice tone="info" title="About availability">
          The data provider lists this site as "{station.provider_status}". That is community-maintained information, not live connector availability.
        </Notice>
      )}

      {/* Charging Bays & Connectors */}
      <div className="bg-white rounded-3xl p-6 sm:p-8 border border-slate-200 shadow-sm space-y-6">
        <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2">
          <Zap className="w-5 h-5 text-brand-600 fill-current" />
          Charging Bays & Connector Standards
        </h2>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {station.points?.map((pt: any) =>
            pt.connectors?.map((conn: any) => (
              <div
                key={conn.id}
                className="p-4 rounded-2xl border border-slate-200 bg-slate-50 flex items-center justify-between"
              >
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-bold text-slate-900">{conn.connector_type}</span>
                    <span className="text-[10px] font-semibold px-2 py-0.5 rounded bg-emerald-100 text-emerald-800">
                      {conn.current_type} {conn.power_kw ? `${conn.power_kw} kW` : "power not stated"}
                    </span>
                  </div>
                  <span className="text-xs text-slate-500 mt-1 block">Bay Point: {pt.point_identifier}</span>
                </div>
                <PriceBlock conn={conn} />
              </div>
            ))
          )}
        </div>
      </div>

      <CostEstimator targetType="station" targetId={station.id} connectors={connectorOptions} />

      {/* Station Metadata & Information */}
      <div className="bg-white rounded-3xl p-6 sm:p-8 border border-slate-200 shadow-sm grid grid-cols-1 md:grid-cols-3 gap-6">
        <div>
          <span className="text-[11px] font-bold uppercase text-slate-400 tracking-wider flex items-center gap-1.5 mb-1">
            <Clock className="w-3.5 h-3.5" /> Operating Hours
          </span>
          <p className="text-sm font-semibold text-slate-800">{station.operating_hours}</p>
        </div>

        <div>
          <span className="text-[11px] font-bold uppercase text-slate-400 tracking-wider flex items-center gap-1.5 mb-1">
            <DollarSign className="w-3.5 h-3.5" /> Parking Fee
          </span>
          <p className="text-sm font-semibold text-slate-800">
            {station.parking_fee === null || station.parking_fee === undefined ? "Parking charges unknown" : station.parking_fee > 0 ? `${inr(station.parking_fee)} / hr` : "No parking charge reported"}
          </p>
        </div>

        <div>
          <span className="text-[11px] font-bold uppercase text-slate-400 tracking-wider flex items-center gap-1.5 mb-1">
            <Database className="w-3.5 h-3.5" /> Data Provenance
          </span>
          <p className="text-xs text-slate-600">{station.data_source}{station.last_synced_at ? `, synced ${new Date(station.last_synced_at).toLocaleString("en-IN")}` : ""}</p>
          {station.source_url && <a href={station.source_url} target="_blank" rel="noopener noreferrer" className="text-xs text-brand-700 underline">View source record</a>}
          {station.attribution && <p className="text-[11px] text-slate-400 mt-1">{station.attribution}</p>}
          {station.usage_cost_text && <p className="text-[11px] text-slate-500 mt-1">Provider pricing note (verbatim): "{station.usage_cost_text}"</p>}
        </div>
      </div>

      {/* Report Modal */}
      <ReportModal
        isOpen={reportModalOpen}
        onClose={() => setReportModalOpen(false)}
        stationId={station.id}
        chargerName={station.name}
        onReportSubmitted={loadStation}
      />
    </div>
  );
}
