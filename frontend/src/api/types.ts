export interface Stats {
  species_count: number;
  observation_count: number;
  photo_count: number;
  audio_count: number;
}

export interface SpeciesSummary {
  id: number;
  catalog_number: string;
  chinese_name: string;
  scientific_name: string;
  order_name: string;
  family_name: string;
  genus_name: string;
  observation_count: number;
  cover_url: string;
}

export interface ObservationSummary {
  id: number;
  catalog_number: string;
  species_name: string;
  species_scientific_name: string;
  observed_at: string;
  locality: string;
  admin1_name: string;
  photo_url: string;
  thumbnail_url: string;
}

export interface ObservationSpeciesEntry {
  id: number | null;
  species_id: number;
  catalog_number?: string;
  species_name: string;
  species_scientific_name: string;
  photo_type: "individual" | "group";
  sex: "male" | "female" | "unknown" | null;
  life_stage: "egg" | "chick" | "subadult" | "adult" | "unknown" | null;
  subspecies: {
    id: number;
    chinese_name: string | null;
    scientific_name: string;
  } | null;
  notes: string | null;
  is_primary: boolean;
}

export interface ObservationRecord {
  id: number;
  species_id: number;
  species_name: string;
  species_scientific_name: string;
  catalog_number: string;
  location: { id: number; catalog_number: string; name: string } | null;
  trip: {
    id: number;
    catalog_number: string;
    name: string;
    started_at: string;
    ended_at: string;
    location_name: string;
  } | null;
  observed_at: string;
  latitude: number;
  longitude: number;
  country_code: string;
  country_name: string;
  admin1_code: string;
  admin1_name: string;
  locality: string;
  season: "spring" | "summer" | "autumn" | "winter" | "other";
  season_note: string | null;
  photo_type: "individual" | "group";
  sex: "male" | "female" | "unknown" | null;
  life_stage: "egg" | "chick" | "subadult" | "adult" | "unknown" | null;
  subspecies: ObservationSpeciesEntry["subspecies"];
  notes: string | null;
  species_count: number;
  species_entries: ObservationSpeciesEntry[];
  photo_asset_id: number;
  photo_url: string;
  thumbnail_url: string;
  audio: Array<{ id: number; asset_id: number; url: string }>;
}

export interface HomepageFeature {
  selection_mode: "manual" | "latest";
  observation: ObservationSummary | null;
}

export interface BackupResult {
  filename: string;
  download_url: string;
  size_bytes: number;
}

export interface RestoreResult {
  message: string;
  safety_backup: { filename: string };
}

export interface UpdateStatus {
  update_available: boolean;
  message: string;
  notes?: string | null;
}

export interface UpdateDownload {
  message: string;
  filename: string;
  download_url: string;
}

export interface IntegrationSummary {
  storage: "portable_local_file";
  amap: {
    configured: boolean;
    key_hint: string | null;
    source: "environment" | "managed" | null;
  };
  llm: {
    provider: "local" | "openai_compatible";
    base_url: string | null;
    model: string | null;
    api_key_configured: boolean;
    api_key_hint: string | null;
  };
  local_model: {
    model: string;
    base_url: string;
  };
}

export interface LocationSummary {
  id: number;
  catalog_number: string;
  name: string;
  location_type: string;
  admin1_name: string;
  city: string | null;
  district: string | null;
  center_latitude: number;
  center_longitude: number;
  species_count: number;
  observation_count: number;
  visit_day_count: number;
  cover_url: string | null;
}

export interface ArchiveSpeciesSummary {
  id: number;
  chinese_name: string;
  scientific_name: string;
  observation_count: number;
  thumbnail_url: string;
}

export interface LocationDetail extends LocationSummary {
  country_code: string;
  country_name: string;
  admin1_code: string;
  coordinate_system: "wgs84" | "gcj02";
  radius_meters: number | null;
  notes: string | null;
  trip_count: number;
  first_observed_at: string | null;
  last_observed_at: string | null;
  cover_source: "custom" | "observation" | null;
  monthly_activity: Array<{ month: string; visit_day_count: number; observation_count: number }>;
  species: ArchiveSpeciesSummary[];
  observations: ObservationRecord[];
  trips: Array<{
    id: number;
    catalog_number: string;
    name: string;
    started_at: string;
    ended_at: string;
    observation_count: number;
    is_primary_location: boolean;
  }>;
}

export interface TripLocationSummary {
  id: number;
  catalog_number: string;
  name: string;
  visit_order?: number;
  is_primary?: boolean;
}

export interface TripSummary {
  id: number;
  catalog_number: string;
  name: string;
  custom_name: string | null;
  location: TripLocationSummary;
  locations: TripLocationSummary[];
  location_count: number;
  started_at: string;
  ended_at: string;
  duration_minutes: number;
  notes: string | null;
  observation_count: number;
  species_count: number;
  genus_count: number;
  family_count: number;
  cover_observation_id: number | null;
  cover_url: string | null;
}

export interface TripDetail extends TripSummary {
  species: ArchiveSpeciesSummary[];
  observations: ObservationRecord[];
}

export type CollectionTemplateKind = "none" | "plumage" | "sex_age" | "custom";

export interface CollectionPlanSummary {
  id: number;
  catalog_number: string;
  name: string;
  introduction: string | null;
  template_kind: CollectionTemplateKind;
  subitems: string[];
  species_count: number;
  slot_count: number;
  completed_count: number;
  cover_url: string | null;
  updated_at: string;
}

export interface CollectionSlot {
  id: number;
  subitem_id: number;
  subitem_label: string;
  label: string;
  observation_species_id: number | null;
  observation_id: number | null;
  photo_url: string | null;
  thumbnail_url: string | null;
  crop_center_x: number;
  crop_center_y: number;
  crop_zoom: number;
}

export interface CollectionMembership {
  id: number;
  species_id: number;
  species_name: string;
  scientific_name: string;
  position: number;
  slots: CollectionSlot[];
}

export interface CollectionPlanDetail extends CollectionPlanSummary {
  memberships: CollectionMembership[];
}
