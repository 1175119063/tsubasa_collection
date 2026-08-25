import sqlite3
from collections.abc import Generator
from datetime import datetime
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import MetaData, create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import Settings

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class Database:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        settings.ensure_directories()
        database_url = f"sqlite:///{settings.database_path.as_posix()}"
        self.engine = create_engine(
            database_url,
            connect_args={"check_same_thread": False, "timeout": 30},
        )
        self.session_factory = sessionmaker(
            bind=self.engine,
            autoflush=False,
            expire_on_commit=False,
            class_=Session,
        )
        self._configure_sqlite(self.engine)

    @staticmethod
    def _configure_sqlite(engine: Engine) -> None:
        @event.listens_for(engine, "connect")
        def set_sqlite_pragmas(dbapi_connection, _connection_record) -> None:  # type: ignore[no-untyped-def]
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys = ON")
            cursor.execute("PRAGMA journal_mode = WAL")
            cursor.execute("PRAGMA busy_timeout = 30000")
            cursor.close()

    def create_schema(self) -> None:
        migrations_dir = Path(__file__).resolve().parent / "migrations"
        config = Config()
        config.set_main_option("script_location", migrations_dir.as_posix())
        config.set_main_option("sqlalchemy.url", str(self.engine.url))
        self._backup_before_migration_if_needed(config)
        command.upgrade(config, "head")

    def _backup_before_migration_if_needed(self, config: Config) -> None:
        if not self.settings.database_path.is_file():
            return
        connection = sqlite3.connect(self.settings.database_path)
        try:
            tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            if not tables:
                return
            current = None
            if "alembic_version" in tables:
                row = connection.execute("SELECT version_num FROM alembic_version").fetchone()
                current = row[0] if row else None
            head = ScriptDirectory.from_config(config).get_current_head()
            if current == head:
                return

            self.settings.backups_dir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
            snapshot_path = self.settings.backups_dir / f"pre-migration-{stamp}.sqlite"
            snapshot = sqlite3.connect(snapshot_path)
            try:
                connection.backup(snapshot)
                result = snapshot.execute("PRAGMA integrity_check").fetchone()
                if result is None or result[0] != "ok":
                    raise RuntimeError("迁移前数据库快照完整性检查失败")
            finally:
                snapshot.close()
        finally:
            connection.close()

    def session(self) -> Generator[Session, None, None]:
        db = self.session_factory()
        try:
            yield db
        finally:
            db.close()
