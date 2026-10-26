"""
Tests for migrate_arc_to_zen.py

Covers:
  Fix — macOS: a process whose command line merely mentions "Zen" is not
        taken for a running Zen browser
"""
import os
import subprocess

import pytest

from migrate_arc_to_zen import Arc2ZenMigrator


def _fake_pgrep(command_lines, calls=None):
    """Fake subprocess.run for `pgrep -f PATTERN` over a process table.

    Like the real pgrep -f: a case-sensitive substring match against each
    command line, exit 0 with the matching pids if any, else exit 1.
    """
    def run(args, **kwargs):
        if calls is not None:
            calls.append(args)
        pattern = args[-1]
        pids = [str(1000 + i) for i, cmd in enumerate(command_lines) if pattern in cmd]
        return subprocess.CompletedProcess(args, 0 if pids else 1,
                                           stdout="\n".join(pids), stderr="")
    return run


class TestZenRunningCheck:
    @pytest.fixture(autouse=True)
    def posix(self, monkeypatch):
        monkeypatch.setattr(os, "name", "posix")

    def test_shell_command_mentioning_zen_is_not_zen(self, monkeypatch):
        monkeypatch.setattr(subprocess, "run", _fake_pgrep([
            '/bin/zsh -c pgrep -fl "Zen.app"; python3 migrate_arc_to_zen.py',
            'vim Zen-notes.md',
        ]))
        assert Arc2ZenMigrator().check_browsers_running() == ([], False)

    @pytest.mark.parametrize("executable", [
        "/Applications/Zen.app/Contents/MacOS/zen",
        "/Users/me/Applications/Zen.app/Contents/MacOS/zen",
    ])
    def test_running_zen_on_macos_is_detected(self, monkeypatch, executable):
        monkeypatch.setattr(subprocess, "run", _fake_pgrep([executable]))
        assert Arc2ZenMigrator().check_browsers_running() == (["Zen"], True)

    def test_windows_queries_zen_process_by_name(self, monkeypatch):
        monkeypatch.setattr(os, "name", "nt")
        calls = []

        def run(args, **kwargs):
            calls.append(args)
            stdout = "\n   Id\n   --\n 4242\n" if 'Get-Process -Name "Zen"' in args[1] else ""
            return subprocess.CompletedProcess(args, 0, stdout=stdout, stderr="")

        monkeypatch.setattr(subprocess, "run", run)
        assert Arc2ZenMigrator().check_browsers_running() == (["Zen"], True)
        assert [c[0] for c in calls] == ["powershell", "powershell"]  # Arc, then Zen
