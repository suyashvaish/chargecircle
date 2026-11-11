"use client";

import React, { useEffect, useState } from "react";

/** Tells people when they are offline or looking at saved public data; never implies a transaction succeeded. */
export function OfflineBanner() {
  const [offline, setOffline] = useState(false);
  const [stale, setStale] = useState(false);
  const [backOnline, setBackOnline] = useState(false);

  useEffect(() => {
    setOffline(!navigator.onLine);
    const off = () => { setOffline(true); setBackOnline(false); };
    const on = () => { setOffline(false); setBackOnline(true); };
    const st = () => setStale(true);
    window.addEventListener("offline", off);
    window.addEventListener("online", on);
    window.addEventListener("cc-stale-data", st);
    return () => { window.removeEventListener("offline", off); window.removeEventListener("online", on); window.removeEventListener("cc-stale-data", st); };
  }, []);

  if (backOnline) {
    return (
      <div role="status" className="bg-emerald-50 border-b border-emerald-200 text-emerald-900 text-xs px-4 py-2 text-center">
        You're back online. <button className="underline font-semibold" onClick={() => location.reload()}>Refresh to load the latest data</button>
      </div>
    );
  }
  if (!offline && !stale) return null;
  return (
    <div role="status" className="bg-amber-50 border-b border-amber-200 text-amber-900 text-xs px-4 py-2 text-center">
      {offline ? "You're offline. Public pages and stations you viewed earlier may be shown from saved data. Bookings and payments need a connection." : "Showing saved public data from this device; it may be out of date."}
    </div>
  );
}
