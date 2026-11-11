import React from "react";
import { Database, FileEdit, Globe2 } from "lucide-react";
import { timeAgo } from "@/lib/format";

/** Says where a record came from, so sample/manual data is never mistaken for live provider data. */
export function DataBadge({ origin, syncedAt }: { origin: string; syncedAt?: string | null }) {
  if (origin === "provider") {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-sky-50 text-sky-800 border border-sky-200">
        <Globe2 className="w-3 h-3" aria-hidden="true" /> Open Charge Map · synced {timeAgo(syncedAt)}
      </span>
    );
  }
  if (origin === "sample") {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-amber-50 text-amber-800 border border-amber-200">
        <Database className="w-3 h-3" aria-hidden="true" /> Sample data · not real
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-slate-100 text-slate-700 border border-slate-200">
      <FileEdit className="w-3 h-3" aria-hidden="true" /> Manually entered
    </span>
  );
}
