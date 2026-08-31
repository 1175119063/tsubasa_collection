from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from .models import (
    CollectionPlan,
    CollectionPlanSlot,
    CollectionPlanSpecies,
    CollectionPlanSubitem,
    Observation,
    ObservationSpecies,
    Species,
)
from .schemas import (
    CollectionPlanInput,
    CollectionPlanSpeciesInput,
    CollectionSlotEvidenceInput,
)
from .service_common import DomainError, normalized_name

COLLECTION_PRESETS = {
    "none": [""],
    "plumage": ["br.", "non br."],
    "sex_age": ["♂", "♀", "juv."],
}


class CollectionServiceMixin:
    def list_collection_plans(self) -> list[dict]:
        plans = self.session.scalars(self._collection_query()).unique().all()
        return [self._collection_dict(plan, detailed=False) for plan in plans]

    def collection_plan_detail(self, plan_id: int) -> dict:
        plan = self.session.scalar(
            self._collection_query().where(CollectionPlan.id == plan_id)
        )
        if plan is None:
            raise DomainError("收集计划不存在", 404)
        return self._collection_dict(plan, detailed=True)

    def create_collection_plan(self, payload: CollectionPlanInput) -> dict:
        plan = CollectionPlan(
            name=payload.name,
            introduction=payload.introduction or None,
            template_kind=payload.template_kind,
        )
        self.session.add(plan)
        self.session.flush()
        self._replace_collection_structure(plan, payload, [])
        self.session.commit()
        return self.collection_plan_detail(plan.id)

    def update_collection_plan(
        self, plan_id: int, payload: CollectionPlanInput
    ) -> dict:
        plan = self.session.scalar(
            self._collection_query().where(CollectionPlan.id == plan_id)
        )
        if plan is None:
            raise DomainError("收集计划不存在", 404)

        saved_evidence = {
            (membership.species_id, slot.subitem.label_key): (
                slot.observation_species_id,
                slot.crop_center_x,
                slot.crop_center_y,
                slot.crop_zoom,
            )
            for membership in plan.memberships
            for slot in membership.slots
        }
        species_ids = [membership.species_id for membership in plan.memberships]
        plan.name = payload.name
        plan.introduction = payload.introduction or None
        plan.template_kind = payload.template_kind
        plan.memberships.clear()
        plan.subitems.clear()
        self.session.flush()
        self._replace_collection_structure(plan, payload, species_ids, saved_evidence)
        self.session.commit()
        return self.collection_plan_detail(plan.id)

    def set_collection_plan_species(
        self, plan_id: int, payload: CollectionPlanSpeciesInput
    ) -> dict:
        plan = self.session.scalar(
            self._collection_query().where(CollectionPlan.id == plan_id)
        )
        if plan is None:
            raise DomainError("收集计划不存在", 404)
        saved_evidence = {
            (membership.species_id, slot.subitem.label_key): (
                slot.observation_species_id,
                slot.crop_center_x,
                slot.crop_center_y,
                slot.crop_zoom,
            )
            for membership in plan.memberships
            for slot in membership.slots
        }
        plan.memberships.clear()
        self.session.flush()
        self._create_collection_memberships(
            plan, payload.species_ids, plan.subitems, saved_evidence
        )
        self.session.commit()
        return self.collection_plan_detail(plan.id)

    def delete_collection_plan(self, plan_id: int) -> dict:
        plan = self.session.get(CollectionPlan, plan_id)
        if plan is None:
            raise DomainError("收集计划不存在", 404)
        self.session.delete(plan)
        self.session.commit()
        return {"deleted": True, "id": plan_id}

    def set_collection_slot_evidence(
        self,
        plan_id: int,
        slot_id: int,
        payload: CollectionSlotEvidenceInput,
    ) -> dict:
        slot = self.session.scalar(
            select(CollectionPlanSlot)
            .join(CollectionPlanSpecies)
            .where(
                CollectionPlanSlot.id == slot_id,
                CollectionPlanSpecies.plan_id == plan_id,
            )
            .options(selectinload(CollectionPlanSlot.membership))
        )
        if slot is None:
            raise DomainError("收集槽位不存在", 404)
        if payload.observation_species_id is None:
            slot.observation_species_id = None
            slot.crop_center_x = 0.5
            slot.crop_center_y = 0.5
            slot.crop_zoom = 1
        else:
            entry = self.session.get(ObservationSpecies, payload.observation_species_id)
            if entry is None:
                raise DomainError("照片凭证对应的观察物种条目不存在", 404)
            if entry.species_id != slot.membership.species_id:
                raise DomainError("照片凭证必须属于当前槽位的物种", 422)
            slot.observation_species_id = entry.id
            slot.crop_center_x = payload.crop_center_x
            slot.crop_center_y = payload.crop_center_y
            slot.crop_zoom = payload.crop_zoom
        self.session.commit()
        return self.collection_plan_detail(plan_id)

    def collection_species_observations(
        self, plan_id: int, species_id: int
    ) -> list[dict]:
        membership = self.session.scalar(
            select(CollectionPlanSpecies).where(
                CollectionPlanSpecies.plan_id == plan_id,
                CollectionPlanSpecies.species_id == species_id,
            )
        )
        if membership is None:
            raise DomainError("该物种不属于当前收集计划", 404)
        observations = self.session.scalars(
            select(Observation)
            .join(ObservationSpecies)
            .where(ObservationSpecies.species_id == species_id)
            .order_by(Observation.observed_at.desc(), Observation.id.desc())
        ).unique().all()
        return [self._observation_dict(item, species_id) for item in observations]

    def _replace_collection_structure(
        self,
        plan: CollectionPlan,
        payload: CollectionPlanInput,
        species_ids: list[int],
        saved_evidence: dict[tuple[int, str], tuple[int | None, float, float, float]]
        | None = None,
    ) -> None:
        labels = (
            payload.subitems
            if payload.template_kind == "custom"
            else COLLECTION_PRESETS[payload.template_kind]
        )
        subitems = [
            CollectionPlanSubitem(
                plan=plan,
                label=label,
                label_key=normalized_name(label) if label else "__default__",
                position=position,
            )
            for position, label in enumerate(labels)
        ]
        self.session.add_all(subitems)
        self.session.flush()

        self._create_collection_memberships(
            plan, species_ids, subitems, saved_evidence
        )

    def _create_collection_memberships(
        self,
        plan: CollectionPlan,
        species_ids: list[int],
        subitems: list[CollectionPlanSubitem],
        saved_evidence: dict[tuple[int, str], tuple[int | None, float, float, float]]
        | None = None,
    ) -> None:

        species_by_id = {
            species.id: species
            for species in self.session.scalars(
                select(Species).where(Species.id.in_(species_ids))
            ).all()
        }
        if len(species_by_id) != len(species_ids):
            raise DomainError("收集计划中包含不存在的物种", 404)
        observed_species_ids = set(
            self.session.scalars(
                select(ObservationSpecies.species_id)
                .where(ObservationSpecies.species_id.in_(species_ids))
                .distinct()
            ).all()
        )
        if observed_species_ids != set(species_ids):
            raise DomainError("收集计划只能加入已有正式观察的物种", 422)

        for position, species_id in enumerate(species_ids):
            membership = CollectionPlanSpecies(
                plan=plan,
                species=species_by_id[species_id],
                position=position,
            )
            self.session.add(membership)
            self.session.flush()
            for subitem in subitems:
                evidence = (saved_evidence or {}).get((species_id, subitem.label_key))
                slot = CollectionPlanSlot(membership=membership, subitem=subitem)
                if evidence:
                    entry_id, slot.crop_center_x, slot.crop_center_y, slot.crop_zoom = evidence
                    entry = self.session.get(ObservationSpecies, entry_id) if entry_id else None
                    slot.observation_species_id = (
                        entry.id if entry is not None and entry.species_id == species_id else None
                    )
                self.session.add(slot)

    @staticmethod
    def _collection_query():
        return (
            select(CollectionPlan)
            .options(
                selectinload(CollectionPlan.subitems),
                selectinload(CollectionPlan.memberships).selectinload(
                    CollectionPlanSpecies.species
                ),
                selectinload(CollectionPlan.memberships)
                .selectinload(CollectionPlanSpecies.slots)
                .selectinload(CollectionPlanSlot.subitem),
                selectinload(CollectionPlan.memberships)
                .selectinload(CollectionPlanSpecies.slots)
                .selectinload(CollectionPlanSlot.observation_species)
                .selectinload(ObservationSpecies.observation)
                .selectinload(Observation.photo_asset),
            )
            .order_by(CollectionPlan.updated_at.desc(), CollectionPlan.id.desc())
        )

    def _collection_dict(self, plan: CollectionPlan, detailed: bool) -> dict:
        slots = [slot for membership in plan.memberships for slot in membership.slots]
        completed = sum(slot.observation_species_id is not None for slot in slots)
        cover_slot = next(
            (slot for slot in slots if slot.observation_species_id is not None), None
        )
        result = {
            "id": plan.id,
            "catalog_number": plan.catalog_number,
            "name": plan.name,
            "introduction": plan.introduction,
            "template_kind": plan.template_kind,
            "subitems": [item.label for item in plan.subitems],
            "species_count": len(plan.memberships),
            "slot_count": len(slots),
            "completed_count": completed,
            "cover_url": (
                self._media_url(cover_slot.observation_species.observation.photo_asset)
                if cover_slot and cover_slot.observation_species
                else None
            ),
            "updated_at": plan.updated_at.isoformat(timespec="minutes"),
        }
        if detailed:
            result["memberships"] = [
                {
                    "id": membership.id,
                    "species_id": membership.species_id,
                    "species_name": membership.species.chinese_name,
                    "scientific_name": membership.species.scientific_name,
                    "position": membership.position,
                    "slots": [
                        self._collection_slot_dict(slot, membership.species.chinese_name)
                        for slot in sorted(
                            membership.slots, key=lambda item: item.subitem.position
                        )
                    ],
                }
                for membership in plan.memberships
            ]
        return result

    def _collection_slot_dict(
        self, slot: CollectionPlanSlot, species_name: str
    ) -> dict:
        entry = slot.observation_species
        observation = entry.observation if entry else None
        return {
            "id": slot.id,
            "subitem_id": slot.subitem_id,
            "subitem_label": slot.subitem.label,
            "label": " ".join(filter(None, (species_name, slot.subitem.label))),
            "observation_species_id": slot.observation_species_id,
            "observation_id": observation.id if observation else None,
            "photo_url": self._media_url(observation.photo_asset) if observation else None,
            "thumbnail_url": (
                self._media_url(observation.photo_asset, thumbnail=True)
                if observation
                else None
            ),
            "crop_center_x": slot.crop_center_x,
            "crop_center_y": slot.crop_center_y,
            "crop_zoom": slot.crop_zoom,
        }
