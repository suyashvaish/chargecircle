import React from "react";
import { AlertTriangle, Info, CheckCircle2, XCircle } from "lucide-react";

type Tone = "info" | "warn" | "error" | "success";
const TONES: Record<Tone, { box: string; Icon: any }> = {
  info: { box: "bg-sky-50 border-sky-200 text-sky-900", Icon: Info },
  warn: { box: "bg-amber-50 border-amber-200 text-amber-900", Icon: AlertTriangle },
  error: { box: "bg-rose-50 border-rose-200 text-rose-900", Icon: XCircle },
  success: { box: "bg-emerald-50 border-emerald-200 text-emerald-900", Icon: CheckCircle2 },
};

export function Notice({ tone = "info", title, children, className = "" }: { tone?: Tone; title?: string; children?: React.ReactNode; className?: string }) {
  const { box, Icon } = TONES[tone];
  return (
    <div role={tone === "error" ? "alert" : "status"} className={`flex gap-2.5 p-3.5 rounded-xl border text-xs leading-relaxed ${box} ${className}`}>
      <Icon className="w-4 h-4 shrink-0 mt-0.5" aria-hidden="true" />
      <div>
        {title && <p className="font-bold mb-0.5">{title}</p>}
        {children}
      </div>
    </div>
  );
}
