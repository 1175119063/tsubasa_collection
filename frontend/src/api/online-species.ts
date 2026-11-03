export interface OnlineTaxonName {
  chinese_name: string | null;
  scientific_name: string | null;
}
export interface OnlineTaxonomyDraft {
  order: OnlineTaxonName;
  family: OnlineTaxonName;
  genus: OnlineTaxonName;
  species: OnlineTaxonName;
}
export interface OnlineCandidate {
  id: number;
  name: string;
  common_name: string | null;
  url: string;
  name_source?: { source_url: string; fetched_at: string; cached: boolean };
}
export interface OnlineTaxon extends OnlineCandidate {
  draft: OnlineTaxonomyDraft;
  summary: string | null;
  conservation: Array<{ status: string; authority: string | null; place: string | null }>;
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
}
