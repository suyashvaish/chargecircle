import React from "react";
import Link from "next/link";
import { Zap, ShieldCheck, Heart, MapPin } from "lucide-react";

export function Footer() {
  return (
    <footer className="bg-slate-900 text-slate-300 border-t border-slate-800">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-8">
          {/* Brand Col */}
          <div className="space-y-4">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-brand-500 flex items-center justify-center text-white">
                <Zap className="w-4 h-4 fill-current" />
              </div>
              <span className="text-xl font-bold text-white tracking-tight">
                Charge<span className="text-brand-400">Circle</span>
              </span>
            </div>
            <p className="text-sm text-slate-400 leading-relaxed">
              India&apos;s verified peer-to-peer EV charging discovery and residential marketplace. Empowering reliable clean mobility.
            </p>
            <div className="flex items-center gap-2 text-xs text-brand-400 bg-brand-950/60 border border-brand-800/40 px-3 py-1.5 rounded-lg w-fit">
              <MapPin className="w-3.5 h-3.5" />
              <span>Optimized for Indian EV Standards (CCS2, Type 2, GB/T)</span>
            </div>
          </div>

          {/* Quick Links */}
          <div>
            <h4 className="text-xs font-semibold text-white uppercase tracking-wider mb-4">
              Discovery & Booking
            </h4>
            <ul className="space-y-2.5 text-sm">
              <li>
                <Link href="/public-chargers" className="hover:text-white transition-colors">
                  Public EV Stations
                </Link>
              </li>
              <li>
                <Link href="/marketplace" className="hover:text-white transition-colors">
                  Home Charging Marketplace
                </Link>
              </li>
              <li>
                <Link href="/map" className="hover:text-white transition-colors">
                  Interactive Live Map
                </Link>
              </li>
              <li>
                <Link href="/host/listings/create" className="hover:text-white transition-colors">
                  Host Onboarding
                </Link>
              </li>
            </ul>
          </div>

          {/* Trust & Safety */}
          <div>
            <h4 className="text-xs font-semibold text-white uppercase tracking-wider mb-4">
              Trust & Safety
            </h4>
            <ul className="space-y-2.5 text-sm">
              <li>
                <Link href="/safety" className="hover:text-white transition-colors flex items-center gap-1.5">
                  <ShieldCheck className="w-4 h-4 text-brand-400" />
                  Electrical Safety Protocol
                </Link>
              </li>
              <li>
                <Link href="/privacy" className="hover:text-white transition-colors">
                  Address Privacy Policy
                </Link>
              </li>
              <li>
                <Link href="/terms" className="hover:text-white transition-colors">
                  Terms of Service
                </Link>
              </li>
              <li>
                <Link href="/support" className="hover:text-white transition-colors">
                  Help & Dispute Center
                </Link>
              </li>
            </ul>
          </div>

          {/* Platform Governance */}
          <div>
            <h4 className="text-xs font-semibold text-white uppercase tracking-wider mb-4">
              Reliability Engine
            </h4>
            <p className="text-xs text-slate-400 leading-relaxed mb-3">
              Operational statuses are calculated via time-decayed evidence: Level 1 (Community reports), Level 2 (Verified charging sessions), Level 3 (Operator telemetry).
            </p>
            <div className="text-xs text-slate-500">
              Payments processed securely via Razorpay sandbox test environment.
            </div>
          </div>
        </div>

        <div className="mt-12 pt-8 border-t border-slate-800 flex flex-col sm:flex-row items-center justify-between gap-4 text-xs text-slate-500">
          <p>© {new Date().getFullYear()} ChargeCircle Technologies India Pvt. Ltd. All rights reserved.</p>
          <p className="flex items-center gap-1">
            Built with integrity for sustainable mobility in India.
          </p>
        </div>
      </div>
    </footer>
  );
}
