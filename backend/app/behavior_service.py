from __future__ import annotations

from uuid import uuid4

from sqlalchemy import select

from .models import ObservationBehavior, ObservationSpecies, SpeciesBehaviorTag
from .service_common import DomainError, normalized_name


class BehaviorServiceMixin:
    def _set_entry_behaviors(self, entry: ObservationSpecies, labels: list[str]) -> None:
        tags = self.session.scalars(
            select(SpeciesBehaviorTag).where(SpeciesBehaviorTag.species_id == entry.species_id)
        ).all()
        by_key = {tag.label_key: tag for tag in tags}
        selected = []
        for label in labels:
            key = normalized_name(label)
            tag = by_key.get(key)
            if tag is None:
                tag = SpeciesBehaviorTag(
                    species_id=entry.species_id, label=label.strip(), label_key=key
                )
                self.session.add(tag)
                self.session.flush()
                by_key[key] = tag
            selected.append(tag)
        wanted = {tag.id for tag in selected}
        existing = {link.tag_id for link in entry.behavior_links}
        for link in list(entry.behavior_links):
            if link.tag_id not in wanted:
                entry.behavior_links.remove(link)
        for tag in selected:
            if tag.id not in existing:
                entry.behavior_links.append(ObservationBehavior(tag=tag))

    def _replace_behavior_tags(self, species, payloads) -> None:
        entries = {entry.observation_id: entry for entry in species.observation_entries}
        by_id = {tag.id: tag for tag in species.behavior_tags}
        by_key = {tag.label_key: tag for tag in species.behavior_tags}
        prepared = []
        used = set()
        for data in payloads:
            tag = (
                by_id.get(data.id) if data.id is not None
                else by_key.get(normalized_name(data.label))
            )
            if data.id is not None and tag is None:
                raise DomainError("行为标签不属于当前物种", 422)
            if tag is not None and tag.id in used:
                raise DomainError("行为标签不能重复", 422)
            ids = data.selected_observation_ids()
            if any(value not in entries for value in ids):
                raise DomainError("行为标签只能关联该物种的观察记录", 422)
            if tag is not None:
                used.add(tag.id)
            prepared.append((tag, data, ids))
        for tag in list(species.behavior_tags):
            if tag.id not in used:
                self.session.delete(tag)
            else:
                tag.label_key = f"__rename_{uuid4().hex}"
        self.session.flush()
        for tag, data, ids in prepared:
            if tag is None:
                tag = SpeciesBehaviorTag(species_id=species.id)
                self.session.add(tag)
            tag.label = data.label
            tag.label_key = normalized_name(data.label)
            tag.observation_id = None
            wanted = {entries[value].id for value in ids}
            existing = {link.observation_species_id for link in tag.entry_links}
            for link in list(tag.entry_links):
                if link.observation_species_id not in wanted:
                    tag.entry_links.remove(link)
            for value in ids:
                if entries[value].id not in existing:
                    tag.entry_links.append(ObservationBehavior(entry=entries[value]))
        self.session.flush()

    def _behavior_dict(self, tag: SpeciesBehaviorTag) -> dict:
        observations = sorted(
            (link.entry.observation for link in tag.entry_links
             if link.entry.species_id == tag.species_id),
            key=lambda item: (item.observed_at, item.id),
        )
        return {
            "id": tag.id, "label": tag.label, "linked": bool(observations),
            "observation_ids": [item.id for item in observations],
            "observations": [
                {**self._proof(item, tag.species_id),
                 "observed_at": item.observed_at.isoformat(timespec="minutes"),
                 "locality": item.locality}
                for item in observations
            ],
            **(self._proof(observations[0], tag.species_id) if observations else {}),
        }

    @staticmethod
    def _entry_behavior_labels(entry: ObservationSpecies) -> list[str]:
        return [link.tag.label for link in sorted(entry.behavior_links, key=lambda v: v.tag.id)
                if link.tag.species_id == entry.species_id]
