import React from "react";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";

export default function TermsPage() {
  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-12 space-y-8">
      <Link
        href="/"
        className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-500 hover:text-slate-900"
      >
        <ArrowLeft className="w-4 h-4" /> Back to Home
      </Link>

      <div className="space-y-2">
        <span className="text-xs font-bold uppercase tracking-wider text-brand-600">Legal Agreement</span>
        <h1 className="text-3xl font-extrabold text-slate-900 tracking-tight">Terms of Service</h1>
        <p className="text-xs text-slate-400">Effective Date: October 2026</p>
      </div>

      <div className="bg-white rounded-3xl p-6 sm:p-8 border border-slate-200 shadow-sm space-y-6 text-xs sm:text-sm text-slate-600 leading-relaxed">
        <div className="space-y-2">
          <h2 className="text-base font-bold text-slate-900">1. Nature of the Platform</h2>
          <p>
            ChargeCircle provides discovery tools for public electric vehicle chargers and an online marketplace facilitating reservations between EV drivers and independent charging facility hosts. ChargeCircle does not own third-party public charging stations.
          </p>
        </div>

        <div className="space-y-2">
          <h2 className="text-base font-bold text-slate-900">2. Host Warranties & Tariff Setting</h2>
          <p>
            Hosts warrant that their electrical installation complies with local safety regulations and that providing access to suitable EV charging facilities complies with applicable state electricity distribution guidelines.
          </p>
        </div>

        <div className="space-y-2">
          <h2 className="text-base font-bold text-slate-900">3. Cancellation & Refund Policy</h2>
          <p>
            Drivers may cancel a reservation up to 2 hours prior to the scheduled slot start time for a full refund minus payment processing expenses. Late cancellations within 2 hours are subject to host parking compensation.
          </p>
        </div>

        <div className="space-y-2">
          <h2 className="text-base font-bold text-slate-900">4. Settlement & Platform Fees</h2>
          <p>
            ChargeCircle deducts a 10% platform facilitation fee on completed marketplace transactions. Host payouts are disbursed through Razorpay or direct bank transfer.
          </p>
        </div>
      </div>
    </div>
  );
}
