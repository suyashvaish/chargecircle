"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { Home, Search, MapPin, ShieldCheck, Star, ArrowRight, Zap, PlusCircle } from "lucide-react";
import { apiRequest } from "@/lib/api";
import { HomeListing } from "@/types";

export default function MarketplacePage() {
  const [listings, setListings] = useState<HomeListing[]>([]);
  const [city, setCity] = useState("Bengaluru");
  const [connectorType, setConnectorType] = useState("");
  const [maxPrice, setMaxPrice] = useState("");
  const [isLoading, setIsLoading] = useState(true);

  const fetchListings = async () => {
    setIsLoading(true);
    try {
      const params = new URLSearchParams();
      if (city) params.append("city", city);
      if (connectorType) params.append("connector_type", connectorType);
      if (maxPrice) params.append("max_price", maxPrice);

      const data = await apiRequest<HomeListing[]>(`/marketplace/listings?${params.toString()}`);
      setListings(data);
    } catch (err) {
      console.error("Failed to fetch marketplace listings:", err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchListings();
  }, [city, connectorType, maxPrice]);

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      {/* Top Banner */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-extrabold text-slate-900 tracking-tight flex items-center gap-2.5">
            <Home className="w-7 h-7 text-blue-600" />
            Home Charging Marketplace
          </h1>
          <p className="text-sm text-slate-600 mt-1">
            Book private residential EV wallboxes from verified hosts. Safe earthing, reserved slots, and zero congestion.
          </p>
        </div>

        <Link
          href="/host/listings/create"
          className="inline-flex items-center gap-2 px-5 py-2.5 bg-brand-600 hover:bg-brand-700 text-white font-semibold text-xs sm:text-sm rounded-xl shadow-md transition-colors shrink-0"
        >
          <PlusCircle className="w-4 h-4" />
          List Your Home Charger
        </Link>
      </div>

      {/* Filter Row */}
      <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm flex flex-wrap items-center gap-4 text-xs">
        <span className="font-semibold text-slate-500 uppercase tracking-wider">Filters:</span>

        {/* City Filter */}
        <select
          value={city}
          onChange={(e) => setCity(e.target.value)}
          className="px-3 py-1.5 bg-slate-50 border border-slate-200 rounded-lg text-slate-700 font-medium"
        >
          <option value="Bengaluru">Bengaluru</option>
          <option value="Mumbai">Mumbai</option>
          <option value="Gurugram">Gurugram</option>
        </select>

        {/* Connector Type */}
        <select
          value={connectorType}
          onChange={(e) => setConnectorType(e.target.value)}
          className="px-3 py-1.5 bg-slate-50 border border-slate-200 rounded-lg text-slate-700 font-medium"
        >
          <option value="">All Connectors</option>
          <option value="Type 2">Type 2 (AC Wallbox)</option>
          <option value="16A 3-Pin Socket">16A 3-Pin Industrial Plug</option>
          <option value="CCS2">CCS2</option>
        </select>

        {/* Max Price */}
        <select
          value={maxPrice}
          onChange={(e) => setMaxPrice(e.target.value)}
          className="px-3 py-1.5 bg-slate-50 border border-slate-200 rounded-lg text-slate-700 font-medium"
        >
          <option value="">Any Tariff</option>
          <option value="12">Under ₹12/kWh</option>
          <option value="15">Under ₹15/kWh</option>
          <option value="20">Under ₹20/kWh</option>
        </select>

        <span className="ml-auto text-slate-400">
          Showing {listings.length} verified residential facilities
        </span>
      </div>

      {/* Listings Grid */}
      {isLoading ? (
        <div className="py-20 text-center text-slate-400">Loading home charging listings...</div>
      ) : listings.length === 0 ? (
        <div className="bg-white p-12 text-center rounded-2xl border border-slate-200">
          <p className="text-slate-600 font-medium">No home chargers currently listed in this area.</p>
          <Link
            href="/host/listings/create"
            className="mt-4 inline-block px-4 py-2 text-xs font-semibold text-brand-600 bg-brand-50 rounded-lg"
          >
            Be the first host in {city}!
          </Link>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {listings.map((item) => (
            <div
              key={item.id}
              className="bg-white rounded-2xl border border-slate-200 overflow-hidden shadow-sm hover:shadow-md transition-shadow flex flex-col justify-between"
            >
              <div>
                {/* Photo Header */}
                <div className="h-44 bg-slate-100 relative overflow-hidden">
                  <img
                    src={
                      item.cover_photo_url ||
                      "https://images.unsplash.com/photo-1593941707882-a5bba14938c7?auto=format&fit=crop&w=800&q=80"
                    }
                    alt={item.title}
                    className="w-full h-full object-cover"
                  />
                  <div className="absolute top-3 left-3 bg-white/95 backdrop-blur-sm text-blue-700 px-2.5 py-1 rounded-md text-[11px] font-bold shadow-sm">
                    {item.connector_type} • {item.power_kw} kW
                  </div>
                  {item.safety_confirmed && (
                    <div className="absolute top-3 right-3 bg-emerald-600 text-white px-2 py-0.5 rounded text-[10px] font-semibold flex items-center gap-1 shadow-sm">
                      <ShieldCheck className="w-3 h-3" />
                      Earthing Verified
                    </div>
                  )}
                </div>

                <div className="p-5">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wide">
                      {item.locality}, {item.city}
                    </span>
                    <div className="flex items-center gap-1 text-xs font-bold text-slate-800">
                      <Star className="w-3.5 h-3.5 fill-amber-400 text-amber-400" />
                      {item.average_rating ? `${item.average_rating} (${item.total_reviews})` : "No reviews yet"}
                    </div>
                  </div>

                  <h3 className="text-base font-bold text-slate-900 leading-snug line-clamp-1 mb-2">
                    {item.title}
                  </h3>
                  <p className="text-xs text-slate-500 line-clamp-2 mb-4 leading-relaxed">
                    {item.description}
                  </p>

                  <div className="flex items-center gap-2 text-xs text-slate-600 pt-2 border-t border-slate-100">
                    <span className="px-2 py-0.5 rounded bg-slate-100 font-medium">
                      {item.property_type.replace("_", " ")}
                    </span>
                    {item.has_covered_parking && (
                      <span className="px-2 py-0.5 rounded bg-slate-100 font-medium">
                        Covered Bay
                      </span>
                    )}
                  </div>
                </div>
              </div>

              <div className="p-5 pt-0">
                <div className="pt-3 border-t border-slate-100 flex items-center justify-between">
                  <div>
                    <span className="text-base font-extrabold text-slate-900">₹{item.price_per_kwh}</span>
                    <span className="text-xs text-slate-500"> / kWh</span>
                  </div>
                  <Link
                    href={`/marketplace/${item.id}`}
                    className="inline-flex items-center gap-1 px-3.5 py-1.5 text-xs font-semibold text-white bg-blue-600 hover:bg-blue-700 rounded-lg shadow-sm transition-colors"
                  >
                    Reserve Slot <ArrowRight className="w-3 h-3" />
                  </Link>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
