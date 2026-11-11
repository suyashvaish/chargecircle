"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  User,
  Car,
  Calendar,
  Clock,
  Heart,
  Zap,
  PlusCircle,
  ArrowRight,
  ShieldCheck,
  MapPin,
} from "lucide-react";
import { apiRequest, getToken } from "@/lib/api";
import { Booking, Vehicle } from "@/types";

export default function DriverDashboardPage() {
  const router = useRouter();
  const [user, setUser] = useState<any>(null);
  const [bookings, setBookings] = useState<Booking[]>([]);
  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [favorites, setFavorites] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  // New vehicle modal
  const [showAddVehicle, setShowAddVehicle] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [make, setMake] = useState("");
  const [model, setModel] = useState("");
  const [year, setYear] = useState(2024);
  const [batteryKwh, setBatteryKwh] = useState("");
  const [maxAc, setMaxAc] = useState("");
  const [maxDc, setMaxDc] = useState("");
  const [plate, setPlate] = useState("");
  const [prefs, setPrefs] = useState("");
  const [connectors, setConnectors] = useState<string[]>([]);
  const [vehicleError, setVehicleError] = useState("");

  const openVehicleForm = (v?: Vehicle) => {
    setVehicleError("");
    setEditingId(v ? v.id : null);
    setMake(v?.make || ""); setModel(v?.model || ""); setYear(v?.year || 2024);
    setBatteryKwh(v?.battery_capacity_kwh != null ? String(v.battery_capacity_kwh) : "");
    setMaxAc(v?.max_ac_charging_kw != null ? String(v.max_ac_charging_kw) : "");
    setMaxDc(v?.max_dc_charging_kw != null ? String(v.max_dc_charging_kw) : "");
    setPlate(v?.license_plate || ""); setPrefs(v?.charging_preferences || "");
    setConnectors(v?.connectors?.map((c) => c.connector_type) || []);
    setShowAddVehicle(true);
  };
  const toggleConnector = (c: string) => setConnectors((cur) => (cur.includes(c) ? cur.filter((x) => x !== c) : [...cur, c]));

  const loadDashboard = async () => {
    try {
      const [uData, bData, vData, fData] = await Promise.all([
        apiRequest<any>("/auth/me"),
        apiRequest<Booking[]>("/marketplace/bookings?role=driver"),
        apiRequest<Vehicle[]>("/users/vehicles"),
        apiRequest<any[]>("/community/favorites"),
      ]);
      setUser(uData);
      setBookings(bData);
      setVehicles(vData);
      setFavorites(fData);
    } catch (err) {
      console.error("Failed to load driver dashboard:", err);
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
    loadDashboard();
  }, []);

  const handleSaveVehicle = async (e: React.FormEvent) => {
    e.preventDefault();
    setVehicleError("");
    const num = (v: string) => (v.trim() === "" ? null : Number(v));
    try {
      await apiRequest(editingId ? `/users/vehicles/${editingId}` : "/users/vehicles", {
        method: editingId ? "PUT" : "POST",
        body: JSON.stringify({
          make: make.trim(), model: model.trim(), year,
          battery_capacity_kwh: num(batteryKwh), max_ac_charging_kw: num(maxAc), max_dc_charging_kw: num(maxDc),
          license_plate: plate.trim() || null, charging_preferences: prefs.trim() || null,
          connector_types: connectors, is_primary: editingId ? vehicles.find((v) => v.id === editingId)?.is_primary : vehicles.length === 0,
        }),
      });
      setShowAddVehicle(false);
      loadDashboard();
    } catch (err: any) {
      setVehicleError(err.message || "Failed to save vehicle");
    }
  };

  if (isLoading) {
    return <div className="py-24 text-center text-slate-400">Loading your EV dashboard...</div>;
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      {/* Top Welcome */}
      <div className="bg-white rounded-3xl p-6 sm:p-8 border border-slate-200 shadow-sm flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <span className="text-[11px] font-bold uppercase tracking-wider text-brand-600">
            Driver Portal
          </span>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 mt-1">
            Welcome, {user?.full_name}
          </h1>
          <p className="text-xs text-slate-500 mt-0.5">{user?.email} • {user?.profile?.preferred_city || "Bengaluru"}</p>
        </div>

        <div className="flex gap-2">
          <Link
            href="/public-chargers"
            className="px-4 py-2 bg-brand-50 hover:bg-brand-100 text-brand-700 font-semibold text-xs rounded-xl border border-brand-200 transition-colors"
          >
            Find Public Charger
          </Link>
          <Link
            href="/marketplace"
            className="px-4 py-2 bg-blue-50 hover:bg-blue-100 text-blue-700 font-semibold text-xs rounded-xl border border-blue-200 transition-colors"
          >
            Book Home Bay
          </Link>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Bookings List (2 cols) */}
        <div className="lg:col-span-2 space-y-6">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2">
              <Calendar className="w-5 h-5 text-brand-600" />
              Your Charging Reservations ({bookings.length})
            </h2>
          </div>

          {bookings.length === 0 ? (
            <div className="p-12 text-center bg-white rounded-2xl border border-slate-200">
              <p className="text-slate-500 text-sm">No reservations yet.</p>
              <Link
                href="/marketplace"
                className="mt-3 inline-block px-4 py-2 text-xs font-semibold text-brand-600 bg-brand-50 rounded-lg"
              >
                Explore Home Chargers
              </Link>
            </div>
          ) : (
            <div className="space-y-4">
              {bookings.map((b) => (
                <div
                  key={b.id}
                  className="bg-white rounded-2xl p-5 border border-slate-200 shadow-sm flex flex-col sm:flex-row sm:items-center justify-between gap-4"
                >
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                        {b.booking_reference}
                      </span>
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${
                          b.status === "confirmed"
                            ? "bg-emerald-50 text-emerald-700"
                            : b.status === "completed"
                            ? "bg-blue-50 text-blue-700"
                            : "bg-slate-100 text-slate-700"
                        }`}
                      >
                        {b.status.replace("_", " ")}
                      </span>
                    </div>

                    <h4 className="text-sm font-bold text-slate-900">
                      {b.full_address || b.listing?.title || "Home Charger Bay"}
                    </h4>

                    <div className="flex items-center gap-4 text-xs text-slate-500">
                      <span className="flex items-center gap-1">
                        <Clock className="w-3.5 h-3.5" />
                        {new Date(b.start_time).toLocaleDateString("en-IN", { day: "numeric", month: "short" })}{" "}
                        {new Date(b.start_time).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" })}
                      </span>
                      <span>₹{b.total_amount}</span>
                    </div>
                  </div>

                  <Link
                    href={`/bookings/${b.id}`}
                    className="inline-flex items-center gap-1 px-4 py-2 text-xs font-semibold text-white bg-brand-600 hover:bg-brand-700 rounded-xl shadow-sm self-start sm:self-center"
                  >
                    View Voucher <ArrowRight className="w-3.5 h-3.5" />
                  </Link>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Vehicles & Favorites Sidebar (1 col) */}
        <div className="lg:col-span-1 space-y-6">
          {/* Configured EV Profile */}
          <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                <Car className="w-4 h-4 text-blue-600" />
                Configured EV Profile
              </h3>
              <button
                onClick={() => openVehicleForm()}
                className="text-xs font-bold text-brand-600 hover:text-brand-700"
              >
                + Add EV
              </button>
            </div>

            {vehicles.length === 0 ? (
              <p className="text-xs text-slate-500">No vehicle registered yet.</p>
            ) : (
              <div className="space-y-3">
                {vehicles.map((v) => (
                  <div key={v.id} className="p-3 rounded-xl bg-slate-50 border border-slate-100 text-xs">
                    <div className="font-bold text-slate-800 text-sm">
                      {v.make} {v.model} ({v.year})
                    </div>
                    <div className="text-slate-500 mt-1 flex justify-between">
                      <span>Battery: {v.battery_capacity_kwh != null ? `${v.battery_capacity_kwh} kWh` : "unknown"}</span>
                      <span>Plate: {v.license_plate || "N/A"}</span>
                    </div>
                    <div className="text-slate-500 mt-1">AC max: {v.max_ac_charging_kw != null ? `${v.max_ac_charging_kw} kW` : "unknown"} · DC max: {v.max_dc_charging_kw != null ? `${v.max_dc_charging_kw} kW` : "unknown"}</div>
                    <div className="flex gap-1 mt-2 items-center flex-wrap">
                      {(!v.connectors || v.connectors.length === 0) && <span className="text-amber-700">Connector types not set: compatibility cannot be confirmed</span>}
                      {v.connectors?.map((c) => (
                        <span key={c.id} className="px-1.5 py-0.5 rounded bg-blue-100 text-blue-800 text-[10px] font-semibold">
                          {c.connector_type}
                        </span>
                      ))}
                      <button onClick={() => openVehicleForm(v)} className="ml-auto text-brand-700 font-semibold underline">Edit</button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Saved Favorites */}
          <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm space-y-4">
            <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
              <Heart className="w-4 h-4 text-rose-500" />
              Saved Favorites ({favorites.length})
            </h3>
            {favorites.length === 0 ? (
              <p className="text-xs text-slate-500">No saved chargers yet.</p>
            ) : (
              <div className="space-y-2">
                {favorites.map((f) => (
                  <div key={f.id} className="p-2.5 rounded-lg bg-slate-50 text-xs">
                    <span className="font-bold text-slate-800 block">{f.title}</span>
                    <span className="text-[11px] text-slate-400">{f.address}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Vehicle profile modal: unknown specs stay blank, nothing is assumed */}
      {showAddVehicle && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm overflow-y-auto" role="dialog" aria-modal="true" aria-label="Vehicle profile">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl">
            <h3 className="text-lg font-bold text-slate-900 mb-1">{editingId ? "Edit" : "Add"} your electric vehicle</h3>
            <p className="text-xs text-slate-500 mb-4">Only fill in what you know. Anything left blank is treated as unknown and used to explain why compatibility cannot be confirmed.</p>
            {vehicleError && <div role="alert" className="mb-3 p-3 rounded-lg bg-rose-50 border border-rose-200 text-xs text-rose-800">{vehicleError}</div>}
            <form onSubmit={handleSaveVehicle} className="space-y-4 text-xs">
              <div className="grid grid-cols-2 gap-3">
                <label className="block font-bold text-slate-700">Make<input required maxLength={100} value={make} onChange={(e) => setMake(e.target.value)} className="w-full mt-1 px-3 py-2 bg-slate-50 border rounded-lg font-normal" placeholder="e.g. Tata" /></label>
                <label className="block font-bold text-slate-700">Model<input required maxLength={100} value={model} onChange={(e) => setModel(e.target.value)} className="w-full mt-1 px-3 py-2 bg-slate-50 border rounded-lg font-normal" placeholder="e.g. Nexon EV" /></label>
              </div>
              <div className="grid grid-cols-3 gap-3">
                <label className="block font-bold text-slate-700">Battery (kWh)<input type="number" step="0.1" min="0.1" max="400" value={batteryKwh} onChange={(e) => setBatteryKwh(e.target.value)} className="w-full mt-1 px-3 py-2 bg-slate-50 border rounded-lg font-normal" placeholder="unknown" /></label>
                <label className="block font-bold text-slate-700">Max AC (kW)<input type="number" step="0.1" min="0.1" max="50" value={maxAc} onChange={(e) => setMaxAc(e.target.value)} className="w-full mt-1 px-3 py-2 bg-slate-50 border rounded-lg font-normal" placeholder="unknown" /></label>
                <label className="block font-bold text-slate-700">Max DC (kW)<input type="number" step="0.1" min="0.1" max="600" value={maxDc} onChange={(e) => setMaxDc(e.target.value)} className="w-full mt-1 px-3 py-2 bg-slate-50 border rounded-lg font-normal" placeholder="unknown" /></label>
              </div>
              <fieldset>
                <legend className="font-bold text-slate-700 mb-1">Connector types your vehicle supports</legend>
                <div className="flex flex-wrap gap-3">
                  {["CCS2", "Type 2", "CHAdeMO", "GB/T", "Bharat AC-001", "16A 3-Pin Socket"].map((c) => (
                    <label key={c} className="flex items-center gap-1.5 font-medium text-slate-700"><input type="checkbox" checked={connectors.includes(c)} onChange={() => toggleConnector(c)} />{c}</label>
                  ))}
                </div>
              </fieldset>
              <label className="block font-bold text-slate-700">Licence plate (optional)<input maxLength={20} value={plate} onChange={(e) => setPlate(e.target.value)} className="w-full mt-1 px-3 py-2 bg-slate-50 border rounded-lg font-normal" /></label>
              <label className="block font-bold text-slate-700">Charging preferences (optional)<input maxLength={500} value={prefs} onChange={(e) => setPrefs(e.target.value)} className="w-full mt-1 px-3 py-2 bg-slate-50 border rounded-lg font-normal" placeholder="e.g. prefer covered parking" /></label>
              <div className="pt-2 flex justify-end gap-2">
                <button type="button" onClick={() => setShowAddVehicle(false)} className="px-4 py-2 font-medium text-slate-600">Cancel</button>
                <button type="submit" className="px-5 py-2 font-bold text-white bg-brand-600 rounded-lg shadow-sm">Save vehicle</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
