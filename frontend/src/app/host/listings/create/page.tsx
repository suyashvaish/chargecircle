"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  Home,
  MapPin,
  Zap,
  ShieldCheck,
  DollarSign,
  ArrowRight,
  ArrowLeft,
  CheckCircle2,
  Lock,
} from "lucide-react";
import { apiRequest, getToken } from "@/lib/api";

export default function CreateListingPage() {
  const router = useRouter();
  const [step, setStep] = useState(1);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");

  // Form State
  const [title, setTitle] = useState("Home Wallbox Charging Point");
  const [description, setDescription] = useState(
    "Safe residential parking space with dedicated wallbox charger. Earthing verified by licensed electrician."
  );
  const [addressStreet, setAddressStreet] = useState("");
  const [locality, setLocality] = useState("");
  const [city, setCity] = useState("Bengaluru");
  const [pinCode, setPinCode] = useState("560034");
  const [latitude, setLatitude] = useState(12.9344);
  const [longitude, setLongitude] = useState(77.6285);

  const [connectorType, setConnectorType] = useState("Type 2");
  const [powerKw, setPowerKw] = useState(7.4);
  const [currentType, setCurrentType] = useState("AC");
  const [propertyType, setPropertyType] = useState("residential_house");
  const [equipmentType, setEquipmentType] = useState("dedicated_wallbox");

  const [pricePerKwh, setPricePerKwh] = useState(12.0);
  const [sessionFee, setSessionFee] = useState(20.0);
  const [parkingFeePerHour, setParkingFeePerHour] = useState(10.0);

  const [safetyConfirmed, setSafetyConfirmed] = useState(true);
  const [earthingVerified, setEarthingVerified] = useState(true);
  const [rcboInstalled, setRcboInstalled] = useState(true);
  const [parkingAccessInstructions, setParkingAccessInstructions] = useState(
    "Enter through the main gate, charger is mounted on the left side wall."
  );

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!getToken()) {
      router.push("/auth/login?redirect=/host/listings/create");
      return;
    }

    setIsSubmitting(true);
    setErrorMessage("");

    try {
      const res = await apiRequest<any>("/marketplace/listings", {
        method: "POST",
        body: JSON.stringify({
          title,
          description,
          address_street: addressStreet,
          locality,
          city,
          state: "Karnataka",
          pin_code: pinCode,
          latitude: Number(latitude),
          longitude: Number(longitude),
          is_address_hidden_until_booked: true,
          property_type: propertyType,
          equipment_type: equipmentType,
          connector_type: connectorType,
          current_type: currentType,
          power_kw: Number(powerKw),
          is_cable_attached: true,
          has_dedicated_meter: true,
          has_covered_parking: true,
          safety_confirmed: safetyConfirmed,
          earthing_verified: earthingVerified,
          rcbo_installed: rcboInstalled,
          price_per_kwh: Number(pricePerKwh),
          session_fee: Number(sessionFee),
          parking_fee_per_hour: Number(parkingFeePerHour),
          minimum_booking_hours: 1.0,
          instant_booking: false,
          parking_access_instructions: parkingAccessInstructions,
          cancellation_policy: "Free cancellation up to 2 hours before booking",
        }),
      });

      router.push("/host/dashboard");
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to create listing");
      setIsSubmitting(false);
    }
  };

  return (
    <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-10 space-y-8">
      <div>
        <Link
          href="/host/dashboard"
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-500 hover:text-slate-900 mb-2"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Host Dashboard
        </Link>
        <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight">
          List Your Home EV Charging Bay
        </h1>
        <p className="text-xs sm:text-sm text-slate-500 mt-1">
          Complete the multi-step verification form to list your residential charger.
        </p>
      </div>

      {/* Progress Steps */}
      <div className="flex items-center justify-between border-b border-slate-200 pb-4 text-xs font-bold">
        <span className={step >= 1 ? "text-brand-600" : "text-slate-400"}>1. Location & Privacy</span>
        <span>&rarr;</span>
        <span className={step >= 2 ? "text-brand-600" : "text-slate-400"}>2. Equipment Specs</span>
        <span>&rarr;</span>
        <span className={step >= 3 ? "text-brand-600" : "text-slate-400"}>3. Pricing & Safety</span>
      </div>

      {errorMessage && (
        <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-xs text-rose-700">
          {errorMessage}
        </div>
      )}

      <form onSubmit={handleSubmit} className="bg-white rounded-3xl p-6 sm:p-8 border border-slate-200 shadow-sm space-y-6">
        {step === 1 && (
          <div className="space-y-4">
            <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
              <MapPin className="w-5 h-5 text-blue-600" />
              Location & Residential Address
            </h3>

            <div>
              <label className="block text-xs font-bold text-slate-700 mb-1">Listing Title</label>
              <input
                type="text"
                required
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-xl text-sm"
              />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">Locality / Sector</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Koramangala 4th Block"
                  value={locality}
                  onChange={(e) => setLocality(e.target.value)}
                  className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-xl text-sm"
                />
              </div>
              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">City</label>
                <select
                  value={city}
                  onChange={(e) => setCity(e.target.value)}
                  className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-xl text-sm"
                >
                  <option value="Bengaluru">Bengaluru</option>
                  <option value="Mumbai">Mumbai</option>
                  <option value="Gurugram">Gurugram</option>
                  <option value="Delhi">Delhi</option>
                </select>
              </div>
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-700 mb-1">
                Full Residential Street Address (Kept Private until Booking Confirmed)
              </label>
              <input
                type="text"
                required
                placeholder="House # / Flat #, Street Name, Landmark"
                value={addressStreet}
                onChange={(e) => setAddressStreet(e.target.value)}
                className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-xl text-sm"
              />
              <p className="text-[11px] text-slate-400 mt-1 flex items-center gap-1">
                <Lock className="w-3.5 h-3.5 text-slate-400" />
                Protected: Drivers cannot view this address until their booking is confirmed.
              </p>
            </div>

            <div className="pt-4 flex justify-end">
              <button
                type="button"
                onClick={() => {
                  if (!locality || !addressStreet) {
                    setErrorMessage("Please fill in locality and address");
                    return;
                  }
                  setErrorMessage("");
                  setStep(2);
                }}
                className="px-6 py-2.5 bg-brand-600 text-white font-semibold text-xs rounded-xl shadow-sm"
              >
                Next: Equipment Specs &rarr;
              </button>
            </div>
          </div>
        )}

        {step === 2 && (
          <div className="space-y-4">
            <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
              <Zap className="w-5 h-5 text-brand-600 fill-current" />
              Charger Configuration & Specifications
            </h3>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">Connector Standard</label>
                <select
                  value={connectorType}
                  onChange={(e) => setConnectorType(e.target.value)}
                  className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-xl text-sm"
                >
                  <option value="Type 2">Type 2 (IEC 62196 Mennekes)</option>
                  <option value="16A 3-Pin Socket">16A 3-Pin Heavy Duty Socket</option>
                  <option value="CCS2">CCS2 (DC / Combo)</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">Rated Power (kW)</label>
                <input
                  type="number"
                  step="0.1"
                  required
                  value={powerKw}
                  onChange={(e) => setPowerKw(Number(e.target.value))}
                  className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-xl text-sm"
                />
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">Equipment Type</label>
                <select
                  value={equipmentType}
                  onChange={(e) => setEquipmentType(e.target.value)}
                  className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-xl text-sm"
                >
                  <option value="dedicated_wallbox">Dedicated Wallbox EVSE</option>
                  <option value="portable_evse">Portable Cable EVSE</option>
                  <option value="industrial_socket">Industrial Socket / Plug</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">Property Type</label>
                <select
                  value={propertyType}
                  onChange={(e) => setPropertyType(e.target.value)}
                  className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-xl text-sm"
                >
                  <option value="residential_house">Independent House / Villa</option>
                  <option value="apartment_parking">Apartment Dedicated Bay</option>
                  <option value="commercial_parking">Office / Commercial Space</option>
                </select>
              </div>
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-700 mb-1">Parking Access Instructions</label>
              <textarea
                rows={2}
                value={parkingAccessInstructions}
                onChange={(e) => setParkingAccessInstructions(e.target.value)}
                placeholder="Gate code, parking slot number, or entry directions for confirmed drivers."
                className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-xl text-sm"
              />
            </div>

            <div className="pt-4 flex justify-between">
              <button
                type="button"
                onClick={() => setStep(1)}
                className="px-4 py-2 text-xs font-semibold text-slate-600 hover:text-slate-900"
              >
                &larr; Back
              </button>
              <button
                type="button"
                onClick={() => setStep(3)}
                className="px-6 py-2.5 bg-brand-600 text-white font-semibold text-xs rounded-xl shadow-sm"
              >
                Next: Pricing & Safety &rarr;
              </button>
            </div>
          </div>
        )}

        {step === 3 && (
          <div className="space-y-4">
            <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
              <DollarSign className="w-5 h-5 text-emerald-600" />
              Pricing & Safety Compliance
            </h3>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">Price per kWh (₹)</label>
                <input
                  type="number"
                  step="0.5"
                  required
                  value={pricePerKwh}
                  onChange={(e) => setPricePerKwh(Number(e.target.value))}
                  className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-xl text-sm"
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">Fixed Session Fee (₹)</label>
                <input
                  type="number"
                  step="1"
                  required
                  value={sessionFee}
                  onChange={(e) => setSessionFee(Number(e.target.value))}
                  className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-xl text-sm"
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">Parking per Hour (₹)</label>
                <input
                  type="number"
                  step="1"
                  required
                  value={parkingFeePerHour}
                  onChange={(e) => setParkingFeePerHour(Number(e.target.value))}
                  className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-xl text-sm"
                />
              </div>
            </div>

            {/* Safety Declarations */}
            <div className="p-4 rounded-2xl bg-emerald-50/70 border border-emerald-200 space-y-3">
              <h4 className="text-xs font-bold text-emerald-900 flex items-center gap-1.5 uppercase tracking-wide">
                <ShieldCheck className="w-4 h-4 text-emerald-600" />
                Mandatory Safety Checklist
              </h4>
              <label className="flex items-start gap-2.5 text-xs text-emerald-950 cursor-pointer">
                <input
                  type="checkbox"
                  checked={safetyConfirmed}
                  onChange={(e) => setSafetyConfirmed(e.target.checked)}
                  className="rounded text-brand-600 mt-0.5"
                />
                <span>I confirm that the equipment is suitable for electric vehicle charging and is inspected.</span>
              </label>
              <label className="flex items-start gap-2.5 text-xs text-emerald-950 cursor-pointer">
                <input
                  type="checkbox"
                  checked={earthingVerified}
                  onChange={(e) => setEarthingVerified(e.target.checked)}
                  className="rounded text-brand-600 mt-0.5"
                />
                <span>I confirm licensed electrical earthing is connected to the charger bay.</span>
              </label>
              <label className="flex items-start gap-2.5 text-xs text-emerald-950 cursor-pointer">
                <input
                  type="checkbox"
                  checked={rcboInstalled}
                  onChange={(e) => setRcboInstalled(e.target.checked)}
                  className="rounded text-brand-600 mt-0.5"
                />
                <span>I confirm an RCBO residual current trip breaker is installed.</span>
              </label>
            </div>

            <div className="pt-4 flex justify-between">
              <button
                type="button"
                onClick={() => setStep(2)}
                className="px-4 py-2 text-xs font-semibold text-slate-600 hover:text-slate-900"
              >
                &larr; Back
              </button>
              <button
                type="submit"
                disabled={isSubmitting || !safetyConfirmed}
                className="px-6 py-2.5 bg-brand-600 hover:bg-brand-700 text-white font-bold text-xs rounded-xl shadow-md transition-colors disabled:opacity-50"
              >
                {isSubmitting ? "Publishing Bay..." : "Publish Home Charger"}
              </button>
            </div>
          </div>
        )}
      </form>
    </div>
  );
}
