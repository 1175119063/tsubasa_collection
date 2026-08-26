from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    app_name: str = "翼·时光记"
    app_version: str = "0.3.0"
    data_dir: Path = PROJECT_ROOT / "data"
    amap_web_service_key: str | None = None
    feather_assistant_enabled: bool = True
    feather_assistant_base_url: str = "http://127.0.0.1:11434"
    feather_assistant_model: str = "feiyu-jingling"
    feather_assistant_timeout_seconds: float = 120.0
    feather_assistant_context_size: int = 8192
    feather_assistant_max_output_tokens: int = 512
    update_manifest_url: str | None = None

    model_config = SettingsConfigDict(
        env_prefix="TSUBASA_",
        env_file=PROJECT_ROOT / ".env",
        extra="ignore",
    )

    @property
    def database_path(self) -> Path:
        return self.data_dir / "database.sqlite"

    @property
    def photos_dir(self) -> Path:
        return self.data_dir / "photos"

    @property
    def thumbnails_dir(self) -> Path:
        return self.data_dir / "thumbnails"

    @property
    def audio_dir(self) -> Path:
        return self.data_dir / "audio"

    @property
    def temp_dir(self) -> Path:
        return self.data_dir / ".tmp"

    @property
    def backups_dir(self) -> Path:
        return self.data_dir.parent / "backups"

    @property
    def integrations_path(self) -> Path:
        return self.data_dir / "integrations.dat"

    @property
    def updates_dir(self) -> Path:
        return self.data_dir.parent / "updates"

    @property
    def knowledge_dir(self) -> Path:
        return self.data_dir / "knowledge"

    def ensure_directories(self) -> None:
        for path in (
            self.data_dir,
            self.photos_dir,
            self.thumbnails_dir,
            self.audio_dir,
            self.temp_dir,
            self.backups_dir,
            self.updates_dir,
            self.knowledge_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)
