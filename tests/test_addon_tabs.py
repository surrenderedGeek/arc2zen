"""
Tests for inject_open_tabs.py --addon-tabs

Covers:
  - only the enabled, non-component extensions of an Arc profile are listed
  - one addons.mozilla.org tab per workspace and add-on, from the space's own profile
  - tabs already in a workspace, and extensions with no known Firefox version, are skipped
"""
import itertools
import json
from types import SimpleNamespace

import inject_open_tabs

KEEPER = "bfogiafebfohielmmehodmfbbebbbpei"     # in EXTENSION_MAP
LASTPASS = "hdokiejnpimakedhajhdlcegeplioahd"   # in EXTENSION_MAP
UNMAPPED = "aaaabbbbccccddddeeeeffffgggghhhh"   # no Firefox version known
AMO = "https://addons.mozilla.org/firefox/addon/{}/"


def _profile(user_data, name, settings):
    for ext_id in settings:
        (user_data / name / "Extensions" / ext_id / "1.0").mkdir(parents=True)
    (user_data / name / "Secure Preferences").write_text(
        json.dumps({"extensions": {"settings": settings}}))


class TestArcEnabledExtensions:
    def test_only_enabled_user_extensions(self, tmp_path):
        _profile(tmp_path, "Default", {
            KEEPER: {"state": 1},
            LASTPASS: {"disable_reasons": [1]},                     # disabled, newer Chromium
            UNMAPPED: {"state": 0},                                 # disabled, older Chromium
            "mhjfbmdgcfjbbpaeojofohoefgiehjai": {"location": 5},    # component extension
        })
        (tmp_path / "Default" / "Extensions" / "Temp").mkdir()
        assert inject_open_tabs.arc_enabled_extensions(str(tmp_path), "Default") == [KEEPER]

    def test_missing_profile(self, tmp_path):
        assert inject_open_tabs.arc_enabled_extensions(str(tmp_path), "Profile 9") == []


class TestAddonTabs:
    def test_tab_per_workspace_from_its_profile(self, tmp_path):
        _profile(tmp_path, "Default", {KEEPER: {"state": 1}, UNMAPPED: {"state": 1}})
        _profile(tmp_path, "Profile 2", {LASTPASS: {}})
        spaces = [SimpleNamespace(space_name="Work", profile="Default"),
                  SimpleNamespace(space_name="Learning", profile="Default"),
                  SimpleNamespace(space_name="Home", profile="Profile 2"),
                  SimpleNamespace(space_name="Gone", profile="Default")]   # no Zen workspace
        ws_map = {"Work": {"uuid": "{w}", "container_id": 2},
                  "Learning": {"uuid": "{l}", "container_id": 2},
                  "Home": {"uuid": "{h}", "container_id": 1}}
        present = {("{h}", AMO.format("lastpass-password-manager"))}     # already open in Home
        ids = itertools.count(1)

        def run():
            return inject_open_tabs.addon_tabs(spaces, ws_map, str(tmp_path), present,
                                               lambda: f"1-{next(ids)}")

        tabs = run()
        assert [(t["zenWorkspace"], t["entries"][0]["url"], t["userContextId"]) for t in tabs] == [
            ("{w}", AMO.format("keeper-password-manager"), 2),
            ("{l}", AMO.format("keeper-password-manager"), 2),
        ]
        assert all(t["pinned"] is False for t in tabs)
        assert len({t["zenSyncId"] for t in tabs}) == 2
        assert run() == [], "a second run must not add the same tabs again"
