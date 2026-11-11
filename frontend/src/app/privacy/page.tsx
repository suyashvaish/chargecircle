import React from "react";
import Link from "next/link";
import { Lock, Shield, ArrowLeft } from "lucide-react";

export default function PrivacyPolicyPage() {
  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-12 space-y-8">
      <Link
        href="/"
        className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-500 hover:text-slate-900"
      >
        <ArrowLeft className="w-4 h-4" /> Back to Home
      </Link>

      <div className="space-y-2">
        <span className="text-xs font-bold uppercase tracking-wider text-brand-600">Trust & Confidentiality</span>
        <h1 className="text-3xl font-extrabold text-slate-900 tracking-tight">
          Privacy Policy & Residential Address Protection
        </h1>
        <p className="text-xs text-slate-400">Last updated: October 2026 • Compliant with Digital Personal Data Protection (DPDP) Act</p>
      </div>

      <div className="bg-white rounded-3xl p-6 sm:p-8 border border-slate-200 shadow-sm space-y-6 text-xs sm:text-sm text-slate-600 leading-relaxed">
        <div className="space-y-2">
          <h2 className="text-base font-bold text-slate-900">1. Residential Address Masking</h2>
          <p>
            ChargeCircle protects the privacy of home charging hosts. Exact house numbers, apartment gate codes, and detailed residential access notes are never publicly indexed or accessible by anonymous visitors. They are only revealed to a driver upon cryptographic confirmation of a paid booking.
          </p>
        </div>

        <div className="space-y-2">
          <h2 className="text-base font-bold text-slate-900">2. Data Minimization & Location Tracking</h2>
          <p>
            We only request your device&apos;s GPS location when you explicitly click &quot;Near Me&quot; or enable geographic filters. We never store background movement traces or continuous location history.
          </p>
        </div>

        <div className="space-y-2">
          <h2 className="text-base font-bold text-slate-900">3. Payment Information Security</h2>
          <p>
            All payment transactions are handled through PCI-DSS compliant providers (Razorpay). ChargeCircle servers never store or handle raw credit card numbers or banking passwords.
          </p>
        </div>

        <div className="space-y-2">
          <h2 className="text-base font-bold text-slate-900">4. Community Reporting Anonymity</h2>
          <p>
            When submitting unverified community operational reports, your account identifier is audited internally to prevent fraud and astroturfing, but is never exposed publicly to other motorists or charging operators.
          </p>
        </div>
      </div>
    </div>
  );
}
