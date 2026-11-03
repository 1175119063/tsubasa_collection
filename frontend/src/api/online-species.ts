export interface OnlineTaxonName {
  chinese_name: string | null;
  scientific_name: string | null;
}
export interface OnlineSubspecies {
  id: number;
  name: string;
  common_name: string | null;
  english_common_name?: string | null;
  rank?: string;
  is_active?: boolean;
  observations_count?: number | null;
  url?: string | null;
  photo?: { attribution: string | null; license: string | null; url: string | null } | null;
}
export interface OnlineTaxonomyDraft {
  order: OnlineTaxonName;
  family: OnlineTaxonName;
  genus: OnlineTaxonName;
  species: OnlineTaxonName;
  subspecies?: OnlineSubspecies[];
}
export interface OnlineCandidate {
  id: number;
  name: string;
  common_name: string | null;
  url: string;
  name_source?: { source_url: string; fetched_at: string; cached: boolean };
}
export interface OnlineConservation {
  status: string;
  authority: string | null;
  place: string | null;
  place_id?: number | null;
  place_display_name?: string | null;
  admin_level?: number | null;
  iucn?: number | null;
  url?: string | null;
  description?: string | null;
  geoprivacy?: string | null;
  updated_at?: string | null;
}
export interface OnlineSubspeciesSuggestion extends OnlineSubspecies {
  confidence: "high" | "medium" | "low";
  reason: string;
}
export interface OnlineAiAdvice {
  available: boolean;
  message?: string | null;
  subspecies: OnlineSubspeciesSuggestion[];
  warnings?: string[];
  sources?: string[];
}
export interface OnlineWikipedia {
  available: boolean;
  title?: string | null;
  url?: string | null;
  lang?: string | null;
  excerpt?: string | null;
  fetched_at?: string | null;
  cached?: boolean;
  message?: string | null;
}
export interface OnlineNearbyCount {
  taxon_id: number;
  name: string;
  common_name: string | null;
  rank?: string;
  count: number;
}
export interface OnlineNearbySubspecies {
  radius_km: number;
  total_results: number;
  returned: number;
  truncated: boolean;
  counts: OnlineNearbyCount[];
  source?: string;
  fetched_at?: string;
  cached?: boolean;
}
export interface OnlineTaxon extends OnlineCandidate {
  draft: OnlineTaxonomyDraft;
  children?: OnlineSubspecies[];
  children_count?: number | null;
  complete_rank?: string | null;
  summary: string | null;
  conservation: OnlineConservation[];
  source_url: string;
  fetched_at: string;
  cached: boolean;
  photo: { attribution: string | null; license: string | null; url: string | null } | null;
}
export interface OnlineSpeciesResult {
  query: string;
  resolved: boolean;
  via: string | null;
  wikidata: { source_url: string; fetched_at: string; cached: boolean } | null;
  taxon: OnlineTaxon | null;
  candidates: OnlineCandidate[];
  warnings: string[];
  nearby?: OnlineNearbySubspecies | null;
  wikipedia?: OnlineWikipedia | null;
  ai?: OnlineAiAdvice | null;
}
