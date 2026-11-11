"use client";

import React, { useState } from "react";
import Link from "next/link";
import { HelpCircle, Mail, MessageSquare, AlertTriangle, ArrowLeft, CheckCircle2 } from "lucide-react";

export default function SupportPage() {
  const [submitted, setSubmitted] = useState(false);
  const [subject, setSubject] = useState("");
  const [message, setMessage] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitted(true);
  };

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-12 space-y-8">
      <Link
        href="/"
        className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-500 hover:text-slate-900"
      >
        <ArrowLeft className="w-4 h-4" /> Back to Home
      </Link>

      <div className="space-y-2">
        <span className="text-xs font-bold uppercase tracking-wider text-brand-600">Customer Support</span>
        <h1 className="text-3xl font-extrabold text-slate-900 tracking-tight">Help & Dispute Resolution</h1>
        <p className="text-sm text-slate-600">
          Have an inquiry regarding a booking, host dispute, or incorrect station report? Our support engineers are here to help.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
        {/* Support Form */}
        <div className="bg-white rounded-3xl p-6 sm:p-8 border border-slate-200 shadow-sm space-y-4">
          <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
            <Mail className="w-5 h-5 text-brand-600" />
            Contact Support Desk
          </h2>

          {submitted ? (
            <div className="p-6 rounded-2xl bg-emerald-50 border border-emerald-200 text-center space-y-2">
              <CheckCircle2 className="w-8 h-8 text-emerald-600 mx-auto" />
              <h3 className="font-bold text-emerald-900 text-sm">Ticket Dispatched</h3>
              <p className="text-xs text-emerald-700">
                Ticket #CC-{Math.floor(100000 + Math.random() * 900000)} created. Our team responds within 4 business hours.
              </p>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-4 text-xs sm:text-sm">
              <div>
                <label className="block font-bold text-slate-700 uppercase tracking-wider text-[11px] mb-1">
                  Inquiry Topic
                </label>
                <select
                  value={subject}
                  onChange={(e) => setSubject(e.target.value)}
                  className="w-full px-3.5 py-2.5 bg-slate-50 border rounded-xl"
                >
                  <option value="booking">Booking / Reservation Issue</option>
                  <option value="payment">Payment or Refund Question</option>
                  <option value="dispute">Host or Driver Dispute</option>
                  <option value="inaccurate_data">Inaccurate Station Status</option>
                </select>
              </div>

              <div>
                <label className="block font-bold text-slate-700 uppercase tracking-wider text-[11px] mb-1">
                  Message Details
                </label>
                <textarea
                  rows={4}
                  required
                  value={message}
                  onChange={(e) => setMessage(e.target.value)}
                  placeholder="Please describe your booking reference, charger location, or concern in detail..."
                  className="w-full px-3.5 py-2.5 bg-slate-50 border rounded-xl"
                />
              </div>

              <button
                type="submit"
                className="w-full py-2.5 bg-brand-600 text-white font-bold text-xs rounded-xl shadow-sm hover:bg-brand-700"
              >
                Submit Ticket
              </button>
            </form>
          )}
        </div>

        {/* FAQs */}
        <div className="space-y-4 text-xs sm:text-sm text-slate-600">
          <div className="bg-white rounded-2xl p-5 border border-slate-200 space-y-1.5">
            <h3 className="font-bold text-slate-900">What if a host charger is occupied when I arrive?</h3>
            <p className="text-xs text-slate-500 leading-relaxed">
              Contact the host directly through the booking voucher or submit a dispute ticket for an immediate automated refund.
            </p>
          </div>

          <div className="bg-white rounded-2xl p-5 border border-slate-200 space-y-1.5">
            <h3 className="font-bold text-slate-900">How long do refunds take?</h3>
            <p className="text-xs text-slate-500 leading-relaxed">
              Refunds initiated on Razorpay sandbox are immediate; live UPI refunds typically credit back within 2-4 hours.
            </p>
          </div>

          <div className="bg-white rounded-2xl p-5 border border-slate-200 space-y-1.5">
            <h3 className="font-bold text-slate-900">How is charger operational status updated?</h3>
            <p className="text-xs text-slate-500 leading-relaxed">
              Community reports decay exponentially every 72 hours. Verified charging sessions carry 3x more weight than unsupported reports.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
