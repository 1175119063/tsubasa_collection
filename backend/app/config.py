from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    app_name: str = "羽迹"
    app_version: str = "0.1.0"
    data_dir: Path = PROJECT_ROOT / "data"

    model_config = SettingsConfigDict(
        env_prefix="YUHEN_",
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

    def ensure_directories(self) -> None:
        for path in (
            self.data_dir,
            self.photos_dir,
            self.thumbnails_dir,
            self.audio_dir,
            self.temp_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)
