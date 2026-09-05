from pathlib import Path


def test_sync_launcher_uses_dedicated_libreoffice_profile():
    text = Path("scripts/orvani-sync-launcher.sh").read_text(encoding="utf-8")

    assert 'PROFILE="${HOME}/.local/share/orvani-sync/libreoffice-profile"' in text
    assert 'mkdir -p "${PROFILE}"' in text
    assert "Path(sys.argv[1]).resolve().as_uri()" in text
    assert '"-env:UserInstallation=${PROFILE_URI}"' in text
