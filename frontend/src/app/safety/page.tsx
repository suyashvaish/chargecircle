import React from "react";
import Link from "next/link";
import { ShieldCheck, Zap, AlertTriangle, CheckCircle2, ArrowLeft } from "lucide-react";

export default function SafetyPage() {
  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-12 space-y-8">
      <Link
        href="/"
        className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-500 hover:text-slate-900"
      >
        <ArrowLeft className="w-4 h-4" /> Back to Home
      </Link>

      <div className="space-y-2">
        <span className="text-xs font-bold uppercase tracking-wider text-brand-600">Compliance & Protection</span>
        <h1 className="text-3xl font-extrabold text-slate-900 tracking-tight">
          EV Charging Safety & Electrical Standards
        </h1>
        <p className="text-sm text-slate-600 leading-relaxed">
          At ChargeCircle, safety is non-negotiable. Learn how our multi-tier electrical inspection rules and peer-to-peer protocols safeguard vehicles, equipment, and residential homes.
        </p>
      </div>

      <div className="space-y-6">
        <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm space-y-3">
          <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
            <CheckCircle2 className="w-5 h-5 text-emerald-600" />
            1. Dedicated Electrical Earthing
          </h2>
          <p className="text-xs sm:text-sm text-slate-600 leading-relaxed">
            All listed host facilities must confirm independent earthing resistance under 2 Ohms. Modern electric vehicles (Tata Nexon, MG ZS EV, Hyundai Ioniq) have onboard safety controllers that will immediately refuse charge if earthing potential is compromised.
          </p>
        </div>

        <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm space-y-3">
          <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
            <CheckCircle2 className="w-5 h-5 text-emerald-600" />
            2. RCBO Residual Current & Overcurrent Breakers
          </h2>
          <p className="text-xs sm:text-sm text-slate-600 leading-relaxed">
            Every charging point must be protected by an RCBO (Residual Current Breaker with Overcurrent protection) with a 30mA trip threshold. This prevents electrical shock hazards in the event of cable insulation wear, monsoons, or vehicle socket degradation.
          </p>
        </div>

        <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm space-y-3">
          <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
            <CheckCircle2 className="w-5 h-5 text-emerald-600" />
            3. Residential Distinctions: Wallbox vs. Ordinary Socket
          </h2>
          <p className="text-xs sm:text-sm text-slate-600 leading-relaxed">
            ChargeCircle clearly categorizes chargers into dedicated EVSE wallboxes (7.4kW - 22kW) versus ordinary 16A industrial sockets. We prohibit makeshift extension cords and uninspected multi-plugs.
          </p>
        </div>

        <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm space-y-3">
          <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
            <CheckCircle2 className="w-5 h-5 text-emerald-600" />
            4. Monsoon & Outdoor Precautions
          </h2>
          <p className="text-xs sm:text-sm text-slate-600 leading-relaxed">
            Charging in wet conditions requires an IP65 rated connector or covered parking bay. Hosts must detail if the charging bay is covered or exposed to rain, allowing drivers to make informed safety choices.
          </p>
        </div>
      </div>
    </div>
  );
}
