"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  Home,
  PlusCircle,
  Calendar,
  DollarSign,
  TrendingUp,
  Clock,
  ShieldCheck,
  CheckCircle2,
  AlertCircle,
  ArrowRight,
} from "lucide-react";
import { apiRequest, getToken } from "@/lib/api";
import { Booking, HomeListing } from "@/types";

export default function HostDashboardPage() {
  const router = useRouter();
  const [listings, setListings] = useState<HomeListing[]>([]);
  const [bookings, setBookings] = useState<Booking[]>([]);
  const [earnings, setEarnings] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  const loadHostData = async () => {
    try {
      const [lData, bData, eData] = await Promise.all([
        apiRequest<HomeListing[]>("/marketplace/my-listings"),
        apiRequest<Booking[]>("/marketplace/bookings?role=host"),
        apiRequest<any[]>("/payments/earnings"),
      ]);
      setListings(lData);
      setBookings(bData);
      setEarnings(eData);
    } catch (err) {
      console.error("Failed to load host dashboard:", err);
      router.push("/auth/login");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (!getToken()) {
      router.push("/auth/login");
      return;
    }
    loadHostData();
  }, []);

  if (isLoading) {
    return <div className="py-24 text-center text-slate-400">Loading host dashboard...</div>;
  }

  const totalEarned = earnings.reduce((acc, curr) => acc + (curr.net_earnings || 0), 0);

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      {/* Top Banner */}
      <div className="bg-white rounded-3xl p-6 sm:p-8 border border-slate-200 shadow-sm flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <span className="text-[11px] font-bold uppercase tracking-wider text-blue-600">
            Host Partner Portal
          </span>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 mt-1">
            Host Dashboard & Earnings
          </h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Manage your residential charging bays, verify earnings, and coordinate driver reservations.
          </p>
        </div>

        <Link
          href="/host/listings/create"
          className="inline-flex items-center gap-2 px-5 py-2.5 bg-brand-600 hover:bg-brand-700 text-white font-semibold text-xs sm:text-sm rounded-xl shadow-md transition-colors shrink-0"
        >
          <PlusCircle className="w-4 h-4" />
          Add Another Bay
        </Link>
      </div>

      {/* Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
          <span className="text-xs font-bold text-slate-400 uppercase tracking-wider flex items-center gap-1.5 mb-1">
            <DollarSign className="w-4 h-4 text-emerald-600" />
            Net Host Earnings
          </span>
          <span className="text-3xl font-extrabold text-slate-900">₹{totalEarned.toFixed(2)}</span>
          <span className="text-xs text-emerald-600 font-semibold block mt-1">Settled automatically via Razorpay</span>
        </div>

        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
          <span className="text-xs font-bold text-slate-400 uppercase tracking-wider flex items-center gap-1.5 mb-1">
            <Calendar className="w-4 h-4 text-blue-600" />
            Reservations Handled
          </span>
          <span className="text-3xl font-extrabold text-slate-900">{bookings.length}</span>
          <span className="text-xs text-slate-500 block mt-1">Across all your listed bays</span>
        </div>

        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
          <span className="text-xs font-bold text-slate-400 uppercase tracking-wider flex items-center gap-1.5 mb-1">
            <Home className="w-4 h-4 text-purple-600" />
            Active Charging Bays
          </span>
          <span className="text-3xl font-extrabold text-slate-900">{listings.length}</span>
          <span className="text-xs text-slate-500 block mt-1">
            {listings.filter((l) => l.status === "approved").length} approved & live
          </span>
        </div>
      </div>

      {/* Your Listings */}
      <div className="space-y-4">
        <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2">
          <Home className="w-5 h-5 text-blue-600" />
          Your Home Charging Listings ({listings.length})
        </h2>

        {listings.length === 0 ? (
          <div className="bg-white p-12 text-center rounded-2xl border border-slate-200">
            <p className="text-slate-600 font-medium">You haven&apos;t published any charging facilities yet.</p>
            <Link
              href="/host/listings/create"
              className="mt-4 inline-block px-5 py-2.5 bg-brand-600 text-white font-semibold text-xs rounded-xl shadow-sm"
            >
              Publish Your First Bay
            </Link>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {listings.map((item) => (
              <div
                key={item.id}
                className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm flex flex-col justify-between"
              >
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs font-bold uppercase tracking-wider text-slate-400">
                      {item.locality}, {item.city}
                    </span>
                    <span
                      className={`px-2.5 py-0.5 rounded text-[11px] font-bold uppercase ${
                        item.status === "approved"
                          ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                          : item.status === "pending_verification"
                          ? "bg-amber-50 text-amber-700 border border-amber-200"
                          : "bg-slate-100 text-slate-700"
                      }`}
                    >
                      {item.status.replace("_", " ")}
                    </span>
                  </div>

                  <h3 className="text-base font-bold text-slate-900">{item.title}</h3>
                  <p className="text-xs text-slate-500 mt-1 line-clamp-2">{item.description}</p>

                  <div className="flex gap-2 mt-4 text-xs">
                    <span className="px-2 py-1 rounded bg-slate-100 font-semibold text-slate-700">
                      {item.connector_type} • {item.power_kw} kW
                    </span>
                    <span className="px-2 py-1 rounded bg-slate-100 font-semibold text-slate-700">
                      ₹{item.price_per_kwh} / kWh
                    </span>
                  </div>
                </div>

                <div className="pt-4 mt-4 border-t border-slate-100 flex items-center justify-between">
                  <span className="text-xs text-slate-400">
                    Session Fee: ₹{item.session_fee} • Parking: ₹{item.parking_fee_per_hour}/h
                  </span>
                  <Link
                    href={`/marketplace/${item.id}`}
                    className="text-xs font-semibold text-blue-600 hover:text-blue-700"
                  >
                    View Public Page &rarr;
                  </Link>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Recent Reservations */}
      <div className="space-y-4">
        <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2">
          <Calendar className="w-5 h-5 text-brand-600" />
          Driver Reservations at Your Bays ({bookings.length})
        </h2>

        {bookings.length === 0 ? (
          <div className="bg-white p-8 text-center rounded-2xl border border-slate-200 text-xs text-slate-500">
            No driver reservations booked yet.
          </div>
        ) : (
          <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden divide-y divide-slate-100">
            {bookings.map((b) => (
              <div key={b.id} className="p-4 sm:p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] font-bold text-slate-400 uppercase">{b.booking_reference}</span>
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${
                        b.status === "confirmed" ? "bg-emerald-50 text-emerald-700" : "bg-slate-100 text-slate-700"
                      }`}
                    >
                      {b.status.replace("_", " ")}
                    </span>
                  </div>
                  <h4 className="text-sm font-bold text-slate-900 mt-1">
                    Slot: {new Date(b.start_time).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" })}
                  </h4>
                  <span className="text-xs text-slate-500">Duration: {b.total_hours} hrs • Est: {b.estimated_kwh} kWh</span>
                </div>

                <div className="flex items-center gap-4">
                  <div className="text-right">
                    <span className="text-sm font-bold text-emerald-600 block">₹{b.host_earnings_amount}</span>
                    <span className="text-[10px] text-slate-400 uppercase">Your Net Payout</span>
                  </div>
                  <Link
                    href={`/bookings/${b.id}`}
                    className="px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-800 text-xs font-semibold rounded-lg"
                  >
                    Details
                  </Link>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
