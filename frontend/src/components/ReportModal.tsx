"use client";

import React, { useState } from "react";
import { AlertCircle, CheckCircle, Upload, X } from "lucide-react";
import { apiRequest } from "@/lib/api";

interface ReportModalProps {
  isOpen: boolean;
  onClose: () => void;
  stationId?: number;
  homeListingId?: number;
  chargerName: string;
  onReportSubmitted?: () => void;
}

export function ReportModal({
  isOpen,
  onClose,
  stationId,
  homeListingId,
  chargerName,
  onReportSubmitted,
}: ReportModalProps) {
  const [category, setCategory] = useState("working_normally");
  const [description, setDescription] = useState("");
  const [evidenceUrl, setEvidenceUrl] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [successMessage, setSuccessMessage] = useState("");

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setErrorMessage("");
    setSuccessMessage("");

    try {
      await apiRequest("/reliability/reports", {
        method: "POST",
        body: JSON.stringify({
          station_id: stationId || null,
          home_listing_id: homeListingId || null,
          category,
          description: description.trim() || undefined,
          evidence_type: evidenceUrl ? "meter_photo" : undefined,
          evidence_file_url: evidenceUrl.trim() || undefined,
        }),
      });

      setSuccessMessage("Thank you! Your operational report has been submitted and evaluated by the Reliability Engine.");
      setTimeout(() => {
        if (onReportSubmitted) onReportSubmitted();
        onClose();
      }, 1500);
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to submit report. Please check if you are signed in.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm">
      <div className="bg-white rounded-2xl max-w-lg w-full p-6 shadow-2xl border border-slate-200">
        <div className="flex justify-between items-center mb-4 pb-3 border-b border-slate-100">
          <div>
            <h3 className="text-lg font-bold text-slate-900">Report Charger Status</h3>
            <p className="text-xs text-slate-500">{chargerName}</p>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600 p-1 rounded-lg">
            <X className="w-5 h-5" />
          </button>
        </div>

        {errorMessage && (
          <div className="mb-4 p-3 rounded-lg bg-rose-50 border border-rose-200 text-xs text-rose-700 flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{errorMessage}</span>
          </div>
        )}

        {successMessage && (
          <div className="mb-4 p-3 rounded-lg bg-emerald-50 border border-emerald-200 text-xs text-emerald-700 flex items-center gap-2">
            <CheckCircle className="w-4 h-4 shrink-0" />
            <span>{successMessage}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
              Current Condition
            </label>
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              className="w-full px-3 py-2 text-sm bg-slate-50 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500"
            >
              <option value="working_normally">✅ Working Normally & Available</option>
              <option value="occupied">⏳ Occupied / Long Queue</option>
              <option value="not_working">❌ Not Working / Power Off</option>
              <option value="damaged_equipment">⚠️ Damaged Equipment / Broken Gun</option>
              <option value="payment_terminal_failure">💳 Payment Terminal / App Failure</option>
              <option value="connector_unavailable">🔌 Connector Type Mismatch / Locked</option>
              <option value="closed_station">🚫 Gate Closed / No Access</option>
              <option value="inaccurate_pricing">💰 Inaccurate Tariff Listed</option>
              <option value="misleading_price">🏷️ Misleading Price (reviewed by our team)</option>
              <option value="suspicious_listing">🕵️ Suspicious Listing (reviewed by our team)</option>
              <option value="unsafe_behavior">🚨 Unsafe Behaviour (reviewed by our team)</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
              Details & Notes (Optional)
            </label>
            <textarea
              rows={3}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="e.g., Gun 2 charged at 58kW. Restroom available."
              className="w-full px-3 py-2 text-sm bg-slate-50 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
              Supporting Evidence URL (Optional)
            </label>
            <div className="flex items-center gap-2">
              <Upload className="w-4 h-4 text-slate-400" />
              <input
                type="url"
                value={evidenceUrl}
                onChange={(e) => setEvidenceUrl(e.target.value)}
                placeholder="https://example.com/meter-photo.jpg"
                className="w-full px-3 py-2 text-sm bg-slate-50 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500"
              />
            </div>
            <p className="text-[11px] text-slate-400 mt-1">
              Level 1 reports are free. Providing photo evidence or charging session records increases reliability weighting.
            </p>
          </div>

          <div className="pt-2 flex justify-end gap-3">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-100 rounded-lg transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="px-5 py-2 text-sm font-medium text-white bg-brand-600 hover:bg-brand-700 rounded-lg shadow-sm transition-colors disabled:opacity-50"
            >
              {isSubmitting ? "Submitting..." : "Submit Report"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
