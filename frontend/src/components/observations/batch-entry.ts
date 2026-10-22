import type { TaxonomyOrder } from "@/api/types";
import { buildObservationPayload, type ObservationDraft } from "./observation-entry";

export interface BatchItem {
  draft: ObservationDraft;
  previewUrl: string;
  selected: boolean;
  state: "draft" | "saving" | "saved" | "error" | "uncertain";
  message: string;
  observationId: number | null;
}
export interface BatchFields { species: boolean; location: boolean; season: boolean }

export function copyBatchFields(source: ObservationDraft, target: ObservationDraft, fields: BatchFields): void {
  if (fields.species) {
    if (target.speciesId !== source.speciesId) target.form.behavior_labels = [];
    target.speciesId = source.speciesId;
    target.orderId = source.orderId;
    target.familyId = source.familyId;
    target.genusId = source.genusId;
    Object.assign(target.newSpecies, source.newSpecies);
    // Individual attributes belong to each photograph; do not copy them implicitly.
    target.form.subspecies_id = null;
    target.additional = target.additional.filter((entry) => String(entry.species.id) !== target.speciesId);
  }
  if (fields.location) {
    const { location_id, latitude, longitude, country_code, country_name, admin1_code, admin1_name, locality } = source.form;
    Object.assign(target.form, { location_id, latitude, longitude, country_code, country_name, admin1_code, admin1_name, locality });
  }
  if (fields.season) target.form.season = source.form.season;
}

export function newSpeciesIdentity(draft: ObservationDraft, taxonomy: TaxonomyOrder[]) {
  const data = buildObservationPayload(draft, taxonomy).new_species;
  if (!data) return null;
  return {
    key: data.scientific_name.normalize("NFKC").trim().replace(/\s+/g, " ").toLocaleLowerCase(),
    signature: JSON.stringify(data),
  };
}
