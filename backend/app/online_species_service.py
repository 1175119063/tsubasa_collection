"""Read-only online species lookup backed by shared sources and one skill."""

import threading
from datetime import datetime
from pathlib import Path

from .inat_mcp import inat_api
from .service_common import DomainError
from .skills.base import SkillContext, SkillError
from .skills.online_species import OnlineSpeciesSkill, enrich_taxon, valid_taxon


class OnlineSpeciesService:
    def __init__(
        self,
        data_dir: Path,
        enabled: bool = True,
        assistant=None,
    ):
        self.enabled = enabled
        self.cache_dir = Path(data_dir) / ".cache" / "inat"
        inat_api.configure(self.cache_dir)
        self.skill = OnlineSpeciesSkill(assistant=assistant)
        self._lock = threading.Lock()

    def status(self) -> dict:
        assistant = self.skill.assistant
        ai_configured = bool(assistant and assistant.enabled)
        return {
            "available": self.enabled,
            "message": (
                "资料来自 iNaturalist 与维基百科；飞羽精灵只整理亚种建议，"
                "不会自动选择或写入数据库。"
                if self.enabled
                else "联网物种查询已关闭。"
            ),
            "sources": ["iNaturalist", "Wikipedia"],
            "ai": {
                "configured": ai_configured,
                "message": (
                    "AI 整理已配置；实际可用性在查询时判断。"
                    if ai_configured
                    else "AI 整理未启用；联网资料仍可查询和预填。"
                ),
            },
        }

    def _run(self, action):
        if not self.enabled:
            raise DomainError("联网物种查询已关闭。", 503)
        if not self._lock.acquire(blocking=False):
            raise DomainError("精灵正在查询物种，请等待当前查询完成后重试。", 429)
        try:
            with inat_api.request_budget(35):
                return action()
        except SkillError as exc:
            raise DomainError(exc.message, exc.status_code) from exc
        except inat_api.InatError as exc:
            raise _domain_error(exc) from exc
        finally:
            self._lock.release()

    @staticmethod
    def _valid_taxon(taxon: dict) -> bool:
        return valid_taxon(taxon)

    @staticmethod
    def _enrich(taxon: dict) -> dict:
        return enrich_taxon(taxon)

    def search(
        self,
        query: str,
        latitude: float | None = None,
        longitude: float | None = None,
        locality: str | None = None,
        observed_at: datetime | None = None,
    ) -> dict:
        context = SkillContext(
            latitude=latitude,
            longitude=longitude,
            locality=locality,
            observed_at=observed_at,
        )
        return self._run(lambda: self.skill.search(query, context))

    def detail(self, taxon_id: int) -> dict:
        return self._run(lambda: self.skill.detail(taxon_id))


def _domain_error(exc: inat_api.InatError) -> DomainError:
    status = exc.status or 0
    text = str(exc) or "未知错误"
    if status == 404:
        return DomainError("未找到该物种，请检查名称或编号。", 404)
    if status == 429:
        return DomainError("资料来源请求过于频繁，请稍后重试。", 429)
    if status in {401, 403}:
        return DomainError("资料来源暂时拒绝访问，请稍后重试。", 503)
    if "超时" in text:
        return DomainError("在线查询超时，请稍后重试或改用学名。", 504)
    if "network error" in text.lower():
        return DomainError("无法连接资料来源，请检查网络后重试。", 503)
    return DomainError("暂时无法获取在线资料，请稍后重试。", 502)
