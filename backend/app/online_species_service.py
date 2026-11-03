"""Explicit, read-only online lookup through the bundled MCP subprocess."""

import re
import threading
from pathlib import Path

from .inat_mcp.mcp_client import McpError, McpStdioClient, McpTimeout, McpToolError
from .service_common import DomainError


class OnlineSpeciesService:
    def __init__(self, data_dir: Path, enabled: bool = True):
        self.enabled = enabled
        self.cache_dir = data_dir / ".cache" / "inat"
        self._lock = threading.Lock()

    def status(self) -> dict:
        return {
            "available": self.enabled,
            "message": "联网查询无需大模型；仅在查询时发送鸟名或物种编号。"
            if self.enabled
            else "联网物种查询已关闭。",
            "sources": ["iNaturalist", "Wikidata"],
        }

    def _call(self, name: str, arguments: dict) -> dict:
        if not self.enabled:
            raise DomainError("联网物种查询已关闭。", 503)
        if not self._lock.acquire(blocking=False):
            raise DomainError("精灵正在查询物种，请等待当前查询完成后重试。", 429)
        try:
            with McpStdioClient(
                env={
                    "TSUBASA_INAT_CACHE_DIR": str(self.cache_dir),
                    "TSUBASA_INAT_ALIASES_DIR": str(self.cache_dir),
                }
            ) as client:
                result = client.call_tool_json(name, arguments, timeout=45)
            if not isinstance(result, dict):
                raise DomainError("在线资料格式异常，请稍后重试。", 502)
            return result
        except McpTimeout as exc:
            raise DomainError("在线查询超时，请稍后重试或改用学名。", 504) from exc
        except McpToolError as exc:
            error = exc.payload.get("error", {}) if isinstance(exc.payload, dict) else {}
            if error.get("status") == 429:
                raise DomainError("资料来源请求过于频繁，请稍后重试。", 429) from exc
            raise DomainError("暂时无法获取在线资料，请检查网络后重试。", 502) from exc
        except (McpError, OSError) as exc:
            raise DomainError("联网查询服务暂时不可用，请稍后重试。", 503) from exc
        finally:
            self._lock.release()

    @staticmethod
    def _valid_taxon(taxon: dict) -> bool:
        return (
            taxon.get("is_bird") is True
            and taxon.get("is_active") is True
            and taxon.get("rank") == "species"
            and bool(taxon.get("name"))
        )

    @staticmethod
    def _enrich(taxon: dict) -> dict:
        def node(item: dict | None) -> dict:
            item = item or {}
            common = item.get("common_name") or ""
            return {
                "chinese_name": common if re.search(r"[\u3400-\u9fff]", common) else None,
                "scientific_name": item.get("name"),
            }

        classification = taxon.get("classification") or {}
        return {
            **taxon,
            "draft": {
                **{rank: node(classification.get(rank)) for rank in ("order", "family", "genus")},
                "species": node(taxon),
            },
        }

    def search(self, query: str) -> dict:
        result = self._call("resolve_name", {"name": query, "use_aliases": False})
        taxon = result.get("taxon")
        warnings = list(result.get("warnings") or [])
        if taxon and not self._valid_taxon(taxon):
            warnings.append("来源匹配到的条目不是有效的鸟类物种，请改用完整学名查询。")
            taxon = None
        candidates = [item for item in result.get("candidates", []) if self._valid_taxon(item)]
        return {
            "query": query,
            "resolved": taxon is not None,
            "via": result.get("via") if taxon else None,
            "wikidata": result.get("wikidata"),
            "taxon": self._enrich(taxon) if taxon else None,
            "candidates": candidates,
            "warnings": warnings,
        }

    def detail(self, taxon_id: int) -> dict:
        taxon = self._call("get_taxon", {"taxon_id": taxon_id})
        if taxon.get("id") != taxon_id or not self._valid_taxon(taxon):
            raise DomainError("该条目不是有效的鸟类物种，无法用于物种录入。", 422)
        return self._enrich(taxon)
