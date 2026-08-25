import hashlib

import pytest
from app.config import Settings
from app.update_service import UpdateError, UpdateService


class StubUpdateService(UpdateService):
    manifest = {
        "version": "0.3.0",
        "installer_url": "https://example.com/yuhen-0.3.0.exe",
        "sha256": hashlib.sha256(b"installer").hexdigest(),
        "notes": "测试更新",
    }

    @staticmethod
    def _request_json(_url: str) -> dict:
        return dict(StubUpdateService.manifest)


def test_update_check_is_unconfigured_by_default(tmp_path):
    service = UpdateService(Settings(_env_file=None, data_dir=tmp_path / "data"))

    result = service.check()

    assert result["configured"] is False
    assert result["update_available"] is False


def test_update_manifest_reports_new_version(tmp_path):
    settings = Settings(
        _env_file=None,
        data_dir=tmp_path / "data",
        app_version="0.2.0",
        update_manifest_url="https://example.com/update-manifest.json",
    )
    result = StubUpdateService(settings).check()

    assert result["update_available"] is True
    assert result["version"] == "0.3.0"
    assert result["notes"] == "测试更新"


@pytest.mark.parametrize(
    "manifest",
    [
        {"version": "0.3", "installer_url": "https://example.com/a.exe", "sha256": "0" * 64},
        {"version": "0.3.0", "installer_url": "http://example.com/a.exe", "sha256": "0" * 64},
        {"version": "0.3.0", "installer_url": "https://example.com/a.exe", "sha256": "bad"},
    ],
)
def test_update_manifest_rejects_unsafe_or_invalid_fields(tmp_path, manifest):
    service = UpdateService(Settings(_env_file=None, data_dir=tmp_path / "data"))

    with pytest.raises(UpdateError):
        service._parse_manifest(manifest)
