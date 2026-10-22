from __future__ import annotations

import csv
import io


def observations_csv(observations: list[dict]) -> bytes:
    """Export one row per species entry while preserving the shared observation ID."""
    output = io.StringIO(newline="")
    fields = [
        "observation_id", "observed_at", "photo_count", "photo_observed_at",
        "species_catalog_number",
        "species_chinese_name", "species_scientific_name", "photo_type", "sex",
        "life_stage", "subspecies_chinese_name", "subspecies_scientific_name",
        "country_code", "country_name", "admin1_code", "admin1_name", "locality",
        "latitude", "longitude", "season", "location_catalog_number", "location_name",
        "trip_catalog_number", "trip_name", "observation_notes", "species_notes", "behavior_labels",
    ]
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\r\n")
    writer.writeheader()
    for observation in observations:
        entries = observation.get("species_entries") or [{
            "species_id": observation.get("species_id"),
            "species_name": observation.get("species_name"),
            "species_scientific_name": observation.get("species_scientific_name"),
            "photo_type": observation.get("photo_type"), "sex": observation.get("sex"),
            "life_stage": observation.get("life_stage"),
            "subspecies": observation.get("subspecies"), "notes": None,
            "behavior_labels": observation.get("behavior_labels", []),
        }]
        for entry in entries:
            subspecies = entry.get("subspecies") or {}
            location = observation.get("location") or {}
            trip = observation.get("trip") or {}
            species_id = entry.get("species_id")
            writer.writerow({
                "observation_id": observation["id"],
                "observed_at": observation["observed_at"],
                "photo_count": observation.get("photo_count", 1),
                "photo_observed_at": " | ".join(
                    photo["observed_at"] for photo in observation.get("photos", [])
                ) or observation["observed_at"],
                "species_catalog_number": (
                    f"AV-{species_id:06d}" if species_id is not None else ""
                ),
                "species_chinese_name": entry.get("species_name"),
                "species_scientific_name": entry.get("species_scientific_name"),
                "photo_type": entry.get("photo_type"), "sex": entry.get("sex"),
                "life_stage": entry.get("life_stage"),
                "subspecies_chinese_name": subspecies.get("chinese_name"),
                "subspecies_scientific_name": subspecies.get("scientific_name"),
                "country_code": observation.get("country_code"),
                "country_name": observation.get("country_name"),
                "admin1_code": observation.get("admin1_code"),
                "admin1_name": observation.get("admin1_name"),
                "locality": observation.get("locality"),
                "latitude": observation.get("latitude"),
                "longitude": observation.get("longitude"),
                "season": observation.get("season"),
                "location_catalog_number": location.get("catalog_number"),
                "location_name": location.get("name"),
                "trip_catalog_number": trip.get("catalog_number"),
                "trip_name": trip.get("name"),
                "observation_notes": observation.get("notes"),
                "species_notes": entry.get("notes"),
                "behavior_labels": " | ".join(entry.get("behavior_labels", [])),
            })
    return b"\xef\xbb\xbf" + output.getvalue().encode("utf-8")
