"""
Tests for inject_open_tabs.py

Covers:
  Fix — Windows: Zen profile found under %APPDATA%
  Fix — Windows: a running Zen is detected (pgrep does not exist there)
  Feature — --zen-profile picks the Zen profile to write to
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest

import inject_open_tabs
import restore_auto_archived


def _fake_run(stdout, calls=None):
    def run(args, **kwargs):
        if calls is not None:
            calls.append(args)
        return subprocess.CompletedProcess(args, 0, stdout=stdout, stderr="")
    return run


class TestWindowsSupport:
    def test_finds_profile_under_appdata(self, tmp_path, monkeypatch):
        profile = tmp_path / "zen" / "Profiles" / "abcd1234.Default (release)"
        profile.mkdir(parents=True)
        (profile / "zen-sessions.jsonlz4").write_bytes(b"")
        monkeypatch.setattr(os, "name", "nt")
        monkeypatch.setenv("APPDATA", str(tmp_path))
        assert Path(inject_open_tabs.find_zen_profile()) == profile

    def test_running_zen_detected_with_tasklist(self, monkeypatch):
        calls = []
        monkeypatch.setattr(os, "name", "nt")
        monkeypatch.setattr(subprocess, "run", _fake_run(
            "zen.exe                      4242 Console    1    350,000 K\n", calls))
        assert inject_open_tabs.is_zen_running() is True
        assert calls[0][0] == "tasklist"

    def test_no_zen_process_on_windows(self, monkeypatch):
        monkeypatch.setattr(os, "name", "nt")
        monkeypatch.setattr(subprocess, "run", _fake_run(
            "INFO: No tasks are running which match the specified criteria.\n"))
        assert inject_open_tabs.is_zen_running() is False


class TestZenProfileOption:
    @pytest.fixture
    def profiles(self, tmp_path, monkeypatch):
        """Two macOS Zen profiles; 'Default (release)' is the most recently used."""
        monkeypatch.setattr(os, "name", "posix")
        monkeypatch.setenv("HOME", str(tmp_path))
        base = tmp_path / "Library" / "Application Support" / "zen" / "Profiles"
        made = {}
        for i, name in enumerate(["k3j2h1g0.IMSAL", "paysq1vz.Default (release)"]):
            profile = base / name
            profile.mkdir(parents=True)
            sessions = profile / "zen-sessions.jsonlz4"
            sessions.write_bytes(b"")
            os.utime(sessions, (1000 + i, 1000 + i))
            made[name] = str(profile)
        return made

    def test_default_is_most_recently_used(self, profiles):
        assert inject_open_tabs.find_zen_profile() == profiles["paysq1vz.Default (release)"]

    def test_named_profile_wins_over_most_recent(self, profiles):
        assert inject_open_tabs.find_zen_profile("IMSAL") == profiles["k3j2h1g0.IMSAL"]

    def test_unknown_name_is_an_error(self, profiles):
        with pytest.raises(FileNotFoundError, match="No Zen profile matching 'VUB'"):
            inject_open_tabs.find_zen_profile("VUB")

    def test_name_matching_several_profiles_is_an_error(self, profiles):
        with pytest.raises(ValueError, match="Several Zen profiles match '\\.'"):
            inject_open_tabs.find_zen_profile(".")

    @pytest.mark.parametrize("script", [inject_open_tabs, restore_auto_archived])
    def test_cli_stops_on_unknown_profile(self, profiles, monkeypatch, capsys, script):
        monkeypatch.setattr(inject_open_tabs, "is_zen_running", lambda: False)
        monkeypatch.setattr(restore_auto_archived, "auto_archived_tabs", lambda: [])
        monkeypatch.setattr(restore_auto_archived, "arc_space_names", lambda: {})
        monkeypatch.setattr(sys, "argv", [script.__name__, "--zen-profile", "VUB"])
        assert script.main() is False
        assert "ERROR: No Zen profile matching 'VUB'" in capsys.readouterr().out
