"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  Shield,
  Users,
  Home,
  Zap,
  Calendar,
  DollarSign,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  FileText,
  Lock,
} from "lucide-react";
import { apiRequest, getToken } from "@/lib/api";
import { AdminMetrics, HomeListing } from "@/types";
import { AdminQueues } from "@/components/AdminQueues";

export default function AdminDashboardPage() {
  const router = useRouter();
  const [metrics, setMetrics] = useState<AdminMetrics | null>(null);
  const [pendingListings, setPendingListings] = useState<HomeListing[]>([]);
  const [auditLogs, setAuditLogs] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState("");

  const loadAdminData = async () => {
    setIsLoading(true);
    setErrorMessage("");
    try {
      const [mData, pData, aData] = await Promise.all([
        apiRequest<AdminMetrics>("/admin/metrics"),
        apiRequest<HomeListing[]>("/admin/pending-listings"),
        apiRequest<any[]>("/admin/audit-logs?limit=15"),
      ]);
      setMetrics(mData);
      setPendingListings(pData);
      setAuditLogs(aData);
    } catch (err: any) {
      setErrorMessage(
        err.message || "Admin access denied. Please ensure you are logged in with an administrator account."
      );
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (!getToken()) {
      router.push("/auth/login?redirect=/admin");
      return;
    }
    loadAdminData();
  }, []);

  const handleModeration = async (targetId: number, action: "approved" | "rejected") => {
    try {
      await apiRequest("/admin/moderation", {
        method: "POST",
        body: JSON.stringify({
          target_type: "listing",
          target_id: targetId,
          action,
          notes: `Safety and earthing requirements verified by administrator.`,
        }),
      });
      loadAdminData();
    } catch (err: any) {
      setErrorMessage(err.message || "Moderation action failed");
    }
  };

  if (isLoading) {
    return <div className="py-24 text-center text-slate-400">Verifying administrator credentials...</div>;
  }

  if (errorMessage) {
    return (
      <div className="max-w-md mx-auto py-24 text-center px-4 space-y-4">
        <Lock className="w-12 h-12 text-rose-500 mx-auto" />
        <h2 className="text-xl font-bold text-slate-900">Administrator Privileges Required</h2>
        <p className="text-xs text-slate-600">{errorMessage}</p>
        <Link
          href="/auth/login"
          className="inline-block px-5 py-2.5 bg-brand-600 text-white font-bold text-xs rounded-xl shadow-sm"
        >
          Sign In with Admin Account
        </Link>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <span className="text-[11px] font-bold uppercase tracking-wider text-purple-700 bg-purple-50 border border-purple-200 px-2.5 py-0.5 rounded-full inline-flex items-center gap-1">
            <Shield className="w-3.5 h-3.5" />
            Platform Governance
          </span>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 mt-1">
            ChargeCircle Administrator Console
          </h1>
          <p className="text-xs text-slate-500">Live database telemetry, host safety verifications, and audit trails.</p>
        </div>
      </div>

      {/* KPI Cards */}
      {metrics && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm">
            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Total Users</span>
            <span className="text-2xl font-extrabold text-slate-900 block mt-1">{metrics.total_users}</span>
            <span className="text-[11px] text-slate-500">{metrics.total_drivers} drivers • {metrics.total_hosts} hosts</span>
          </div>

          <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm">
            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Total Bookings</span>
            <span className="text-2xl font-extrabold text-slate-900 block mt-1">{metrics.total_bookings}</span>
            <span className="text-[11px] text-emerald-600 font-semibold">{metrics.confirmed_bookings} confirmed</span>
          </div>

          <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm">
            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Gross Revenue</span>
            <span className="text-2xl font-extrabold text-slate-900 block mt-1">₹{metrics.total_gross_revenue}</span>
            <span className="text-[11px] text-slate-500">Platform Fees: ₹{metrics.total_platform_fees}</span>
          </div>

          <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm">
            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Pending Review</span>
            <span className="text-2xl font-extrabold text-amber-600 block mt-1">
              {metrics.pending_host_verifications}
            </span>
            <span className="text-[11px] text-slate-500">Listings awaiting audit</span>
          </div>
        </div>
      )}

      {/* Pending Listings Moderation */}
      <div className="space-y-4">
        <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2">
          <AlertTriangle className="w-5 h-5 text-amber-600" />
          Pending Host Listings Requiring Safety Verification ({pendingListings.length})
        </h2>

        {pendingListings.length === 0 ? (
          <div className="bg-white p-8 text-center rounded-2xl border border-slate-200 text-xs text-slate-500">
            No home charger listings currently awaiting administrator verification.
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {pendingListings.map((l) => (
              <div key={l.id} className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm space-y-3">
                <div className="flex justify-between items-start">
                  <div>
                    <h4 className="font-bold text-slate-900 text-sm">{l.title}</h4>
                    <span className="text-xs text-slate-500">{l.locality}, {l.city} • Host ID: {l.host_id}</span>
                  </div>
                  <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-50 text-amber-700 border border-amber-200">
                    Pending Safety Audit
                  </span>
                </div>

                <div className="text-xs text-slate-600 bg-slate-50 p-3 rounded-xl space-y-1">
                  <div><strong>Address:</strong> {l.display_address}</div>
                  <div><strong>Equipment:</strong> {l.connector_type} • {l.power_kw} kW ({l.equipment_type})</div>
                  <div><strong>Tariff:</strong> ₹{l.price_per_kwh}/kWh + ₹{l.session_fee} session</div>
                </div>

                <div className="flex justify-end gap-2 pt-1">
                  <button
                    onClick={() => handleModeration(l.id, "rejected")}
                    className="px-3.5 py-1.5 bg-rose-50 hover:bg-rose-100 text-rose-700 text-xs font-semibold rounded-lg border border-rose-200"
                  >
                    Reject
                  </button>
                  <button
                    onClick={() => handleModeration(l.id, "approved")}
                    className="px-4 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold rounded-lg shadow-sm"
                  >
                    Approve Listing
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Immutable Audit Trail */}
      <div className="space-y-4">
        <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2">
          <FileText className="w-5 h-5 text-purple-600" />
          Platform Security Audit Log
        </h2>

        <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden divide-y divide-slate-100 text-xs">
          {auditLogs.map((log) => (
            <div key={log.id} className="p-3.5 sm:px-5 flex items-center justify-between">
              <div>
                <span className="font-bold text-slate-800">{log.action}</span>
                <span className="text-slate-500 ml-2">
                  Target: {log.resource_type} (ID: {log.resource_id || "N/A"})
                </span>
                {log.details_json && (
                  <span className="text-[11px] text-slate-400 block font-mono mt-0.5 truncate max-w-xl">
                    {log.details_json}
                  </span>
                )}
              </div>
              <span className="text-slate-400 text-[11px] shrink-0">
                {new Date(log.created_at).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" })}
              </span>
            </div>
          ))}
        </div>
      </div>
      {!errorMessage && <AdminQueues />}
    </div>
  );
}
