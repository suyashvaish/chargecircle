import React from "react";
import { CheckCircle2, AlertTriangle, XCircle, HelpCircle, ShieldCheck, Database } from "lucide-react";

interface StatusBadgeProps {
  status: string;
  confidence?: number;
  isSample?: boolean;
}

export function StatusBadge({ status, confidence, isSample }: StatusBadgeProps) {
  if (isSample) {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-50 text-amber-800 border border-amber-200">
        <Database className="w-3.5 h-3.5 text-amber-600" />
        Sample Benchmark
      </span>
    );
  }

  const s = status?.toLowerCase() || "";

  if (s.includes("confirmed") || s.includes("recently confirmed")) {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-800 border border-emerald-200">
        <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
        Recently Confirmed Operational {confidence ? `(${Math.round(confidence * 100)}%)` : ""}
      </span>
    );
  }

  if (s.includes("likely") || s.includes("working")) {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-50 text-green-700 border border-green-200">
        <CheckCircle2 className="w-3.5 h-3.5 text-green-600" />
        Likely Operational
      </span>
    );
  }

  if (s.includes("unavailable") || s.includes("not working") || s.includes("faulted")) {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-rose-50 text-rose-700 border border-rose-200">
        <XCircle className="w-3.5 h-3.5 text-rose-600" />
        Reported Unavailable
      </span>
    );
  }

  if (s.includes("conflict")) {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-orange-50 text-orange-700 border border-orange-200">
        <AlertTriangle className="w-3.5 h-3.5 text-orange-600" />
        Conflicting Reports
      </span>
    );
  }

  return (
    <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-slate-700 border border-slate-200">
      <HelpCircle className="w-3.5 h-3.5 text-slate-500" />
      Not Recently Checked
    </span>
  );
}
