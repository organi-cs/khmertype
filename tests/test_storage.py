import json

from khmertyper.storage import Settings, Store, data_dir


def result(wpm, acc=95.0, lang="km", mode="time", value=30, **extra):
    return {"lang": lang, "mode": mode, "mode_value": value, "wpm": wpm, "accuracy": acc,
            "keystrokes": 100, "missed": [], **extra}


def test_data_dir_respects_env(isolated_home):
    assert data_dir() == isolated_home


def test_personal_bests_per_mode_and_language():
    store = Store()
    assert store.add_result(result(30)) == (True, None)
    is_pb, prev = store.add_result(result(25))
    assert not is_pb and prev["wpm"] == 30
    is_pb, prev = store.add_result(result(35))
    assert is_pb and prev["wpm"] == 30
    assert store.add_result(result(10, lang="en"))[0]       # separate language
    assert store.add_result(result(10, value=60))[0]        # separate duration
    assert store.personal_best("km", "time", 30)["wpm"] == 35
    assert len(store.history) == 5


def test_equal_speed_breaks_tie_on_accuracy():
    store = Store()
    store.add_result(result(30, acc=90))
    assert store.add_result(result(30, acc=95))[0]
    assert not store.add_result(result(30, acc=95))[0]


def test_round_trip_through_json(isolated_home):
    store = Store()
    store.settings.theme = "nord"
    store.settings.lang = "en"
    store.add_result(result(40, series={"wpm": [1, 2]}, missed=[["ក្រ", 2]]))
    again = Store()
    assert again.settings.theme == "nord" and again.settings.lang == "en"
    assert again.history[0]["missed"] == [["ក្រ", 2]]
    assert "series" not in again.bests["km:time:30"]  # PBs stay small
    raw = (isolated_home / "history.json").read_text(encoding="utf-8")
    assert "ក្រ" in raw  # stored as readable UTF-8, not \\u escapes


def test_corrupt_file_is_kept_aside_not_lost(isolated_home):
    isolated_home.mkdir(parents=True)
    (isolated_home / "history.json").write_text("{not json", encoding="utf-8")
    store = Store()
    assert store.history == []
    backups = list(isolated_home.glob("history.corrupt-*.json"))
    assert len(backups) == 1 and backups[0].read_text() == "{not json"


def test_unknown_or_invalid_settings_fall_back():
    s = Settings.from_dict({"lang": "fr", "time": 45, "words": 25, "future_option": 1})
    assert s.lang == "km" and s.time == 30 and s.words == 25


def test_most_missed_across_history():
    store = Store()
    store.add_result(result(30, missed=[["ក្រ", 2], ["ស្ត្រី", 1]]))
    store.add_result(result(31, missed=[["ស្ត្រី", 3]]))
    store.add_result(result(31, lang="en", missed=[["q", 9]]))
    assert store.most_missed("km") == [("ស្ត្រី", 4), ("ក្រ", 2)]


def test_history_file_is_valid_json(isolated_home):
    Store().add_result(result(20))
    data = json.loads((isolated_home / "history.json").read_text(encoding="utf-8"))
    assert data["version"] == 1 and len(data["history"]) == 1
