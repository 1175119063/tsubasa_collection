import { api, ApiError, errorMessage } from "@/api/client";
import type { LocationSummary, SpeciesSummary, TaxonomyOrder } from "@/api/types";

export interface Subspecies { id: number; chinese_name: string | null; scientific_name: string }
export interface AdditionalSpecies {
  species: SpeciesSummary;
  photo_type: "individual" | "group";
  sex: string;
  life_stage: string;
  subspecies_id: number | null;
  subspecies: Subspecies[];
  notes: string;
}
export type EntryLocation = LocationSummary & { country_code?: string; country_name?: string; admin1_code?: string };
export interface CreationResult { observation_id: number; species_id: number; catalog_number: string }
export interface AdditionalPhotoDraft {
  id: string;
  file: File;
  observed_at: string;
  includesPrimary: boolean;
  speciesIds: number[];
  status: string;
  error: string;
  reading: boolean;
}

export function createObservationDraft(speciesId = "", batch = false) {
  return {
    id: crypto.randomUUID(),
    speciesId,
    orderId: "new", familyId: "new", genusId: "new",
    newSpecies: {
      order_chinese: "", order_scientific: "", family_chinese: "", family_scientific: "",
      genus_chinese: "", genus_scientific: "", chinese_name: "", scientific_name: "",
      iucn_status: "NE", china_status: "", has_subspecies: false, subspecies_list: "",
    },
    form: {
      photo_type: "individual" as "individual" | "group", sex: "unknown", life_stage: "unknown",
      subspecies_id: null as number | null,
      observed_at: batch ? "" : new Date(Date.now() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 16),
      season: "", latitude: null as number | null, longitude: null as number | null,
      country_code: "CN", country_name: "中国", admin1_code: "", admin1_name: "", locality: "",
      notes: "", location_id: "",
    },
    photo: null as File | null,
    additionalPhotos: [] as AdditionalPhotoDraft[],
    primaryPhotoIncludesPrimary: true,
    primaryPhotoSpeciesIds: [] as number[],
    coverPhotoId: "primary",
    audio: [] as File[],
    additional: [] as AdditionalSpecies[],
    photoStatus: "选择照片后将自动读取 EXIF 拍摄时间。",
    photoError: "",
    readingPhoto: false,
  };
}
export type ObservationDraft = ReturnType<typeof createObservationDraft>;

export function resolveTaxon(draft: ObservationDraft, taxonomy: TaxonomyOrder[], level: "order" | "family" | "genus") {
  const order = taxonomy.find((item) => String(item.id) === draft.orderId);
  const family = order?.families.find((item) => String(item.id) === draft.familyId);
  const genus = family?.genera.find((item) => String(item.id) === draft.genusId);
  const selected = { order, family, genus }[level];
  return selected
    ? { chinese_name: selected.chinese_name, scientific_name: selected.scientific_name }
    : { chinese_name: draft.newSpecies[`${level}_chinese`], scientific_name: draft.newSpecies[`${level}_scientific`] };
}

export function parseSubspecies(text: string) {
  return text.split(/\r?\n/).map((line) => line.trim()).filter(Boolean).map((line) => {
    const [scientific, chinese] = line.split("|").map((part) => part.trim());
    return { scientific_name: scientific || "", chinese_name: chinese || null };
  });
}

export function buildObservationPayload(draft: ObservationDraft, taxonomy: TaxonomyOrder[], resolvedSpeciesId?: number) {
  const { form, newSpecies } = draft;
  const isNew = draft.speciesId === "new" && !resolvedSpeciesId;
  const individual = form.photo_type === "individual";
  return {
    species_id: isNew ? null : resolvedSpeciesId || Number(draft.speciesId),
    location_id: form.location_id ? Number(form.location_id) : null,
    new_species: isNew ? {
      order: resolveTaxon(draft, taxonomy, "order"), family: resolveTaxon(draft, taxonomy, "family"),
      genus: resolveTaxon(draft, taxonomy, "genus"), chinese_name: newSpecies.chinese_name,
      scientific_name: newSpecies.scientific_name, iucn_status: newSpecies.iucn_status,
      china_protection_status: newSpecies.china_status || null, has_subspecies: newSpecies.has_subspecies,
      subspecies: newSpecies.has_subspecies ? parseSubspecies(newSpecies.subspecies_list) : [], notes: null,
    } : null,
    subspecies_id: draft.speciesId !== "new" && individual ? form.subspecies_id : null,
    subspecies_scientific_name: null,
    photo_type: form.photo_type, observed_at: form.observed_at,
    latitude: form.latitude, longitude: form.longitude, country_code: form.country_code,
    country_name: form.country_name, admin1_code: form.admin1_code, admin1_name: form.admin1_name,
    locality: form.locality, season: form.season, season_note: null,
    sex: individual ? form.sex : null, life_stage: individual ? form.life_stage : null,
    notes: form.notes || null,
    additional_species: draft.additional.map((item) => ({
      species_id: item.species.id, photo_type: item.photo_type,
      sex: item.photo_type === "individual" ? item.sex : null,
      life_stage: item.photo_type === "individual" ? item.life_stage : null,
      subspecies_id: item.photo_type === "individual" ? item.subspecies_id : null,
      notes: item.notes || null,
    })),
    photos: [
      {
        observed_at: form.observed_at,
        includes_primary: draft.primaryPhotoIncludesPrimary,
        species_ids: draft.primaryPhotoSpeciesIds,
        is_cover: draft.coverPhotoId === "primary",
      },
      ...draft.additionalPhotos.map((item) => ({
        observed_at: item.observed_at,
        includes_primary: item.includesPrimary,
        species_ids: item.speciesIds,
        is_cover: draft.coverPhotoId === item.id,
      })),
    ],
  };
}

// Preflight shared by the visible single form and every item in the batch queue.
// The existing backend remains authoritative for taxonomy and relationship validation.
export function observationIssues(draft: ObservationDraft, taxonomy: TaxonomyOrder[]): string[] {
  const issues: string[] = [];
  const { form } = draft;
  if (!draft.photo) issues.push("请选择 JPEG/JPG 照片");
  if (draft.readingPhoto) issues.push("正在读取照片");
  if (draft.photoError) issues.push(draft.photoError);
  if (draft.additionalPhotos.some((item) => item.reading)) issues.push("正在读取照片");
  issues.push(...draft.additionalPhotos.map((item) => item.error).filter(Boolean));
  if (draft.additionalPhotos.some((item) => !item.observed_at || Number.isNaN(Date.parse(item.observed_at)))) issues.push("请填写每张照片的拍摄时间");
  if (draft.additionalPhotos.length > 19) issues.push("一笔观察最多保存 20 张照片");
  if (!draft.speciesId) issues.push("请选择目标物种");
  if (draft.speciesId === "new") {
    const data = buildObservationPayload(draft, taxonomy).new_species!;
    if ([data.order, data.family, data.genus].some((item) => !item.chinese_name.trim() || !item.scientific_name.trim())
      || !data.chinese_name.trim() || data.scientific_name.trim().length < 3) issues.push("请补全新物种名称和分类");
    if (data.has_subspecies && (!data.subspecies.length || data.subspecies.some((item) => !item.scientific_name))) issues.push("请填写完整亚种名单");
  }
  if (!form.observed_at || Number.isNaN(Date.parse(form.observed_at))) issues.push("请填写拍摄时间");
  if (!form.season) issues.push("请选择季节");
  if (form.latitude === null || typeof form.latitude !== "number" || !Number.isFinite(form.latitude) || Math.abs(form.latitude) > 90) issues.push("请填写有效纬度");
  if (form.longitude === null || typeof form.longitude !== "number" || !Number.isFinite(form.longitude) || Math.abs(form.longitude) > 180) issues.push("请填写有效经度");
  if (!form.country_code.trim() || !form.country_name.trim() || !form.admin1_code.trim() || !form.admin1_name.trim() || !form.locality.trim()) issues.push("请补全国家、行政区和具体地点");
  if (draft.additional.some((item) => String(item.species.id) === draft.speciesId)) issues.push("主要物种与附加物种不能重复");
  if (!draft.primaryPhotoIncludesPrimary && !draft.primaryPhotoSpeciesIds.length) issues.push("封面照片至少关联一个物种");
  if (draft.additionalPhotos.some((item) => !item.includesPrimary && !item.speciesIds.length)) issues.push("每张照片至少关联一个物种");
  return issues;
}

export async function readAdditionalPhoto(file: File): Promise<AdditionalPhotoDraft> {
  const item: AdditionalPhotoDraft = {
    id: crypto.randomUUID(), file, observed_at: "", includesPrimary: true,
    speciesIds: [], status: "正在读取 EXIF 拍摄时间…", error: "", reading: true,
  };
  if (!/\.jpe?g$/i.test(file.name) || file.size > 10 * 1024 * 1024 || !file.size) {
    item.error = "照片必须是非空 JPEG/JPG，且不超过 10 MB";
    item.status = item.error; item.reading = false; return item;
  }
  const body = new FormData(); body.append("photo", file);
  try {
    const result = await api<{ observed_at: string | null }>("/api/media/exif-time", { method: "POST", body });
    item.observed_at = result.observed_at || "";
    item.status = result.observed_at ? `EXIF 拍摄时间：${result.observed_at.replace("T", " ")}` : "没有可用的 EXIF 拍摄时间，请手动填写。";
  } catch (caught) { item.status = errorMessage(caught); if (caught instanceof ApiError && caught.status === 422) item.error = item.status; }
  finally { item.reading = false; }
  return item;
}

export async function readObservationPhoto(draft: ObservationDraft, file: File | null): Promise<void> {
  draft.photo = file;
  draft.photoError = "";
  draft.readingPhoto = false;
  if (!file) { draft.photoStatus = "请选择 JPEG/JPG 照片。"; return; }
  if (!/\.jpe?g$/i.test(file.name) || file.size > 10 * 1024 * 1024 || !file.size) {
    draft.photoError = "照片必须是非空 JPEG/JPG，且不超过 10 MB";
    draft.photoStatus = draft.photoError;
    return;
  }
  draft.readingPhoto = true;
  draft.photoStatus = "正在读取 EXIF 拍摄时间…";
  const previousTime = draft.form.observed_at;
  const body = new FormData();
  body.append("photo", file);
  try {
    const result = await api<{ observed_at: string | null }>("/api/media/exif-time", { method: "POST", body });
    if (draft.photo !== file) return;
    if (result.observed_at) {
      // A late EXIF response must not overwrite a time the user has already edited.
      if (draft.form.observed_at === previousTime) draft.form.observed_at = result.observed_at;
      draft.photoStatus = `EXIF 拍摄时间：${result.observed_at.replace("T", " ")}`;
    } else draft.photoStatus = "照片中没有可用的 EXIF 拍摄时间，请手动填写。";
  } catch (caught) {
    if (draft.photo !== file) return;
    draft.photoStatus = errorMessage(caught);
    if (caught instanceof ApiError && caught.status === 422) draft.photoError = draft.photoStatus;
    else draft.photoStatus += "；可重新读取，或手动填写拍摄时间。";
  } finally {
    if (draft.photo === file) draft.readingPhoto = false;
  }
}

export function applyObservationLocation(draft: ObservationDraft, location: EntryLocation): void {
  Object.assign(draft.form, {
    location_id: String(location.id), latitude: location.center_latitude, longitude: location.center_longitude,
    country_code: location.country_code || "CN", country_name: location.country_name || "中国",
    admin1_code: location.admin1_code || "", admin1_name: location.admin1_name, locality: location.name,
  });
}

export async function saveObservationDraft(draft: ObservationDraft, taxonomy: TaxonomyOrder[], resolvedSpeciesId?: number): Promise<CreationResult> {
  const body = new FormData();
  body.append("payload", JSON.stringify(buildObservationPayload(draft, taxonomy, resolvedSpeciesId)));
  body.append("photo", draft.photo!);
  draft.additionalPhotos.forEach((item) => body.append("additional_photos", item.file));
  draft.audio.forEach((file) => body.append("audio", file));
  return api<CreationResult>("/api/observations", { method: "POST", body });
}

export function isUncertainSave(error: unknown): boolean {
  return !(error instanceof ApiError) || error.status >= 500 || error.status === 408;
}
