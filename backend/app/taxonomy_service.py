"""Explicit, previewed taxonomy edits; names never implicitly merge branches."""

import hashlib
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete, select, text, update

from .models import Family, Genus, ObservationSpecies, Species, TaxonomicOrder
from .schemas import TaxonNodeInput
from .service_common import DomainError, normalized_name

TaxonomyRank = Literal["order", "family", "genus", "species"]
RANKS = ("order", "family", "genus", "species")
MODELS = (TaxonomicOrder, Family, Genus, Species)
PARENTS = (None, "order_id", "family_id", "genus_id")


class TaxonomyEditInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["rename", "move"]
    name: TaxonNodeInput | None = None
    parent_id: int | None = Field(default=None, gt=0)
    # Ordered new ancestors, e.g. family then genus, under parent_id (an order).
    new_parents: list[TaxonNodeInput] = Field(default_factory=list, max_length=3)


class TaxonomyApplyInput(TaxonomyEditInput):
    preview_token: str = Field(min_length=64, max_length=64)


class TaxonomyServiceMixin:
    def _taxonomy_node(self, level, node_id):
        node = self.session.get(MODELS[level], node_id)
        if node is None:
            raise DomainError("分类节点不存在，请刷新后重试", 404)
        return node

    def _taxonomy_path(self, level, node):
        path = []
        while node is not None:
            path.insert(0, {
                "rank": RANKS[level], "id": node.id,
                "chinese_name": node.chinese_name, "scientific_name": node.scientific_name,
            })
            node = self._taxonomy_node(level - 1, getattr(node, PARENTS[level])) if level else None
            level -= 1
        return path

    def _taxonomy_unique(self, level, name, except_id=None):
        existing = self.session.scalar(select(MODELS[level]).where(
            MODELS[level].scientific_name_key == normalized_name(name.scientific_name)
        ))
        if existing is not None and existing.id != except_id:
            raise DomainError("该学名的分类节点已存在，请选择已有节点；本次不会合并节点", 409)

    def preview_taxonomy_edit(self, rank: TaxonomyRank, node_id: int, payload):
        level = RANKS.index(rank)
        node = self._taxonomy_node(level, node_id)
        before = self._taxonomy_path(level, node)
        if payload.action == "rename":
            if not payload.name or payload.parent_id or payload.new_parents:
                raise DomainError("修改名称仅填写中文名与拉丁学名", 422)
            self._taxonomy_unique(level, payload.name, node_id)
            after = [*before[:-1], {**before[-1], **payload.name.model_dump()}]
        else:
            if level == 0 or payload.name or len(payload.new_parents) > level:
                raise DomainError("请选择当前节点的上一级分类，鸟纲与目的归属不可调整", 422)
            ancestor_level = level - len(payload.new_parents) - 1
            if ancestor_level >= 0:
                if not payload.parent_id:
                    raise DomainError("请选择上级分类", 422)
                parent = self._taxonomy_node(ancestor_level, payload.parent_id)
                after = self._taxonomy_path(ancestor_level, parent)
            else:
                if payload.parent_id is not None:
                    raise DomainError("新目只能归入鸟纲", 422)
                after = []
            for offset, name in enumerate(payload.new_parents, ancestor_level + 1):
                self._taxonomy_unique(offset, name)
                after.append({"rank": RANKS[offset], "id": None, **name.model_dump()})
            after.append(before[-1])
        if before == after:
            raise DomainError("分类没有变化", 422)

        descendants = select(Species).join(Genus).join(Family).join(TaxonomicOrder).where(
            MODELS[level].id == node_id
        ).order_by(Species.id)
        species = list(self.session.scalars(descendants))
        species_ids = [item.id for item in species]
        observation_ids = sorted(set(self.session.scalars(select(
            ObservationSpecies.observation_id
        ).where(ObservationSpecies.species_id.in_(species_ids)))))
        result = {
            "rank": rank, "node_id": node_id, "action": payload.action,
            "before": before, "after": after,
            "species": [{"id": item.id, "chinese_name": item.chinese_name,
                         "scientific_name": item.scientific_name} for item in species],
            "species_count": len(species_ids), "observation_count": len(observation_ids),
        }
        # Include descendants' paths: a changed branch cannot reuse an old impact preview.
        fingerprint = {**result, "observation_ids": observation_ids,
                       "paths": [self._taxonomy_path(3, item) for item in species]}
        result["preview_token"] = hashlib.sha256(json.dumps(
            fingerprint, ensure_ascii=False, sort_keys=True
        ).encode()).hexdigest()
        return result

    def apply_taxonomy_edit(self, rank: TaxonomyRank, node_id: int, payload):
        # Serialize validation and writes in SQLite, so a preview cannot become stale mid-save.
        self.session.execute(text("BEGIN IMMEDIATE"))
        try:
            preview = self.preview_taxonomy_edit(rank, node_id, payload)
            if preview["preview_token"] != payload.preview_token:
                raise DomainError("分类或受影响记录已经变化，请重新预览后保存", 409)
            level = RANKS.index(rank)
            if payload.action == "rename":
                values = {**payload.name.model_dump(),
                          "scientific_name_key": normalized_name(payload.name.scientific_name)}
            else:
                parent_id = payload.parent_id
                start = level - len(payload.new_parents)
                for offset, name in enumerate(payload.new_parents, start):
                    values = {**name.model_dump(),
                              "scientific_name_key": normalized_name(name.scientific_name)}
                    if offset:
                        values[PARENTS[offset]] = parent_id
                    parent = MODELS[offset](**values)
                    self.session.add(parent)
                    self.session.flush()
                    parent_id = parent.id
                values = {PARENTS[level]: parent_id}
            self.session.execute(update(MODELS[level]).where(
                MODELS[level].id == node_id
            ).values(**values))
            self.session.flush()
            # Only remove now-empty ancestors of the moved node; never delete its descendants.
            if payload.action == "move":
                for ancestor in reversed(preview["before"][:-1]):
                    index = RANKS.index(ancestor["rank"])
                    child = MODELS[index + 1]
                    if self.session.scalar(select(child.id).where(
                        getattr(child, PARENTS[index + 1]) == ancestor["id"]
                    ).limit(1)) is not None:
                        break
                    self.session.execute(delete(MODELS[index]).where(
                        MODELS[index].id == ancestor["id"]
                    ))
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        return {"rank": rank, "node_id": node_id}
