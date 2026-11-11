export interface User {
  id: number;
  email: string;
  full_name: string;
  phone_number?: string;
  is_active: boolean;
  is_verified: boolean;
  avatar_url?: string;
  roles: { id: number; role_name: string }[];
  profile?: {
    bio?: string;
    preferred_city?: string;
    preferred_language?: string;
    emergency_contact?: string;
  };
  created_at: string;
}

export interface Vehicle {
  id: number;
  user_id: number;
  make: string;
  model: string;
  year: number;
  trim?: string;
  battery_capacity_kwh?: number | null; // null = unknown
  max_ac_charging_kw?: number | null;
  max_dc_charging_kw?: number | null;
  charging_preferences?: string | null;
  license_plate?: string;
  is_primary: boolean;
  connectors: { id: number; connector_type: string }[];
  created_at: string;
}

export interface PublicStation {
  id: number;
  external_id?: string;
  name: string;
  operator_name: string;
  address: string;
  locality?: string;
  city: string;
  state: string;
  pin_code: string;
  latitude: number;
  longitude: number;
  distance_km?: number;
  access_type: string;
  operating_hours: string;
  is_open_24_7: boolean;
  parking_fee?: number | null; // INR/hour, null = unknown
  is_sample: boolean;
  data_source: string;
  data_origin: "provider" | "sample" | "manual";
  source_url?: string | null;
  last_synced_at?: string | null;
  provider_last_verified_at?: string | null;
  provider_status?: string | null;
  usage_cost_text?: string | null;
  membership_required?: boolean | null;
  pay_at_location?: boolean | null;
  price_summary: string;
  price_status: string;
  min_price_per_kwh?: number | null;
  compatibility?: Compatibility | null;
  connectors_summary: string[];
  max_power_kw?: number;
  current_status: string;
  confidence_score: number;
  last_verified_at?: string;
  created_at: string;
  general_notes?: string;
}

export interface Compatibility {
  status: "compatible" | "unconfirmed" | "incompatible";
  reasons: string[];
  effective_power_kw?: number | null;
  power_note?: string | null;
}

export interface ProviderMeta {
  provider: string;
  status: string;
  message: string;
  fetched_at?: string | null;
  radius_km_used?: number | null;
  radius_limited: boolean;
  count: number;
}

export interface EstimateLine { label: string; amount: number | null; basis: string; known: boolean }
export interface Estimate {
  kind: string; currency: string; energy_kwh: number; lines: EstimateLine[]; total_known: number; is_complete: boolean;
  price_confidence: string; excluded: string[]; assumptions: string[]; price_source?: string | null; price_source_label?: string | null;
  price_updated_at?: string | null; price_verified: boolean; connector_id?: number; connector_label?: string;
}

export interface HomeListing {
  id: number;
  host_id: number;
  title: string;
  description: string;
  locality: string;
  city: string;
  state: string;
  pin_code: string;
  latitude: number;
  longitude: number;
  distance_km?: number;
  property_type: string;
  equipment_type: string;
  connector_type: string;
  current_type: string;
  power_kw: number;
  is_cable_attached: boolean;
  has_covered_parking: boolean;
  price_per_kwh: number;
  session_fee: number;
  parking_fee_per_hour: number;
  minimum_booking_hours: number;
  status: string;
  instant_booking: boolean;
  safety_confirmed: boolean;
  earthing_verified: boolean;
  display_address: string;
  location_is_approximate: boolean;
  compatibility?: Compatibility | null;
  exact_latitude?: number | null;
  exact_longitude?: number | null;
  address_street?: string;
  parking_access_instructions?: string;
  cancellation_policy?: string;
  cover_photo_url?: string;
  average_rating?: number | null;
  total_reviews: number;
  created_at: string;
  photos?: { id: number; photo_url: string; caption?: string; is_cover: boolean }[];
  host?: {
    id: number;
    full_name: string;
    is_verified: boolean;
    avatar_url?: string;
    rating: number;
    review_count: number;
  };
}

export interface Booking {
  id: number;
  booking_reference: string;
  driver_id: number;
  listing_id: number;
  vehicle_id?: number;
  start_time: string;
  end_time: string;
  total_hours: number;
  estimated_kwh: number;
  rate_per_kwh: number;
  session_fee: number;
  parking_fee: number;
  subtotal_amount: number;
  platform_fee: number;
  total_amount: number;
  host_earnings_amount: number;
  status: string;
  cancellation_reason?: string;
  arrival_instructions_revealed: boolean;
  full_address?: string;
  parking_access_instructions?: string;
  exact_latitude?: number | null;
  exact_longitude?: number | null;
  approx_latitude?: number | null;
  approx_longitude?: number | null;
  listing_title?: string | null;
  payment_hold_expires_at?: string | null;
  cancelled_at?: string | null;
  payment_status?: string | null;
  created_at: string;
  listing?: HomeListing;
}

export interface ReliabilityScore {
  operational_status: string;
  confidence_score: number;
  evidence_summary: string;
  total_reports_evaluated: number;
  positive_weight: number;
  negative_weight: number;
  last_reported_at?: string;
  calculated_at: string;
}

export interface AdminMetrics {
  total_users: number;
  total_drivers: number;
  total_hosts: number;
  total_public_stations: number;
  total_home_listings: number;
  pending_host_verifications: number;
  total_bookings: number;
  confirmed_bookings: number;
  total_gross_revenue: number;
  total_platform_fees: number;
  pending_reports_moderation: number;
  open_disputes: number;
}
