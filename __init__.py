# Deck Completion Stats Add-on
# Adds a Tools menu item that opens a window displaying statistics.

from __future__ import annotations

from pathlib import Path
from typing import Optional, Tuple, Any, cast
import json

from aqt import mw, gui_hooks
from aqt.qt import *  # noqa: F401,F403
from aqt.utils import qconnect, showInfo
from aqt.webview import AnkiWebView
from anki.decks import DeckId
from anki.models import NotetypeId

from .analytics import learning_history, time_spent_stats, difficult_cards, streak_days, time_studied_history
from .data_access import (
    deck_card_count,
    list_decks,
    list_models,
    model_templates,
    model_name,
    template_progress,
)

ADDON_NAME = "Deck Completion Stats"
ADDON_MODULE = __name__

# Config helpers -------------------------------------------------------------


def get_config() -> dict:
    cfg = mw.addonManager.getConfig(ADDON_MODULE) or {}
    cfg.setdefault("selected_deck_id", None)
    cfg.setdefault("selected_model_id", None)
    cfg.setdefault("selected_model_templates", None)
    cfg.setdefault("granularity", "days")
    cfg.setdefault("progress_forecast_enabled", False)
    cfg.setdefault("word_field_index", 1)
    return cfg


def set_config(cfg: dict) -> None:
    mw.addonManager.writeConfig(ADDON_MODULE, cfg)


def get_selected_deck_id() -> Optional[int]:
    return get_config().get("selected_deck_id")  # type: ignore[return-value]


def set_selected_deck_id(did: Optional[int]) -> None:
    cfg = get_config()
    cfg["selected_deck_id"] = did
    set_config(cfg)


def get_selected_model_id() -> Optional[int]:
    return get_config().get("selected_model_id")  # type: ignore[return-value]


def set_selected_model_id(mid: Optional[int]) -> None:
    cfg = get_config()
    cfg["selected_model_id"] = mid
    cfg["selected_model_templates"] = None
    set_config(cfg)


def get_selected_template_ords() -> Optional[list[int]]:
    return get_config().get("selected_model_templates")  # type: ignore[return-value]


def set_selected_template_ords(ords: Optional[list[int]]) -> None:
    cfg = get_config()
    cfg["selected_model_templates"] = ords
    set_config(cfg)


def get_granularity() -> str:
    return get_config().get("granularity", "days")


def set_granularity(g: str) -> None:
    cfg = get_config()
    cfg["granularity"] = g
    set_config(cfg)


def is_forecast_enabled() -> bool:
    return bool(get_config().get("progress_forecast_enabled", False))


def set_forecast_enabled(on: bool) -> None:
    cfg = get_config()
    cfg["progress_forecast_enabled"] = on
    set_config(cfg)


def get_word_field_index() -> int:
    return int(get_config().get("word_field_index", 1))


def set_word_field_index(i: int) -> None:
    cfg = get_config()
    cfg["word_field_index"] = i
    set_config(cfg)


def selected_deck_name() -> str:
    did = get_selected_deck_id()
    if did is None:
        return "All Decks"
    deck = mw.col.decks.get(cast(DeckId, did)) if mw.col else None
    if not deck:
        set_selected_deck_id(None)
        return "All Decks"
    return deck["name"]


# UI creation ----------------------------------------------------------------


def show_statistics_window() -> None:
    if not mw.col:
        return
    existing = getattr(mw, "deckcompletionstats_dialog", None)
    if existing and existing.isVisible():
        refresh_web(existing)
        existing.raise_()
        existing.activateWindow()
        return
    dialog = QDialog(mw)
    dialog.setWindowTitle(ADDON_NAME)
    dialog.setModal(False)
    layout = QVBoxLayout(dialog)
    web = AnkiWebView(dialog)
    layout.addWidget(web)
    dialog.resize(1000, 800)
    dialog._web = web  # type: ignore[attr-defined]
    mw.deckcompletionstats_dialog = dialog  # type: ignore[attr-defined]
    load_web_content(dialog)
    dialog.show()


def current_count() -> int:
    return deck_card_count(get_selected_deck_id())


def build_state_json() -> str:
    state: dict[str, Any] = {
        "count": current_count(),
        "deckName": selected_deck_name(),
        "modelName": model_name(get_selected_model_id()),
        "granularity": get_granularity(),
        "streak": streak_days(get_selected_deck_id()),
        "wordFieldIndex": get_word_field_index(),
    }
    mid = get_selected_model_id()
    if mid is not None:
        tmpls = model_templates(mid)
        state["templates"] = [
            {"ord": t.get("ord"), "name": t.get("name") or f"Card {t.get('ord',0)+1}"}
            for t in tmpls
        ]
        try:
            mdl = next((m for m in list_models() if m.get("id") == mid), None)
            if mdl:
                state["fieldNames"] = [f.get("name", "") for f in mdl.get("flds", [])]
        except Exception:
            state["fieldNames"] = []
        sel = get_selected_template_ords()
        if sel is not None:
            state["selectedTemplates"] = sel
        progress = template_progress(
            mid,
            sel,
            get_selected_deck_id(),
            get_granularity(),
            forecast=is_forecast_enabled(),
        )
        state["progress"] = progress
        state["forecastEnabled"] = is_forecast_enabled()
        state["learningHistory"] = learning_history(
            mid, sel, get_selected_deck_id(), get_granularity()
        )
        state["timeSpent"] = time_spent_stats(
            mid, sel, get_selected_deck_id(), word_field_index=get_word_field_index()
        )
        state["timeStudied"] = time_studied_history(
            mid, sel, get_selected_deck_id(), get_granularity()
        )
        # Derived high-level metrics
        try:
            progress_series = state.get("progress", {}).get("series", []) or []
            studied_sum = 0
            total_sum = 0
            for s in progress_series:
                data = s.get("data") or []
                if data:
                    studied_sum += (data[-1] or 0)
                total_sum += s.get("totalCards", 0) or 0
            completion_pct = (studied_sum / total_sum * 100) if total_sum > 0 else 0.0
            state["completionPercent"] = round(completion_pct, 1)
            state["studiedCardsCount"] = studied_sum
            ts = state.get("timeStudied", {}).get("totalSecondsAll", 0) or 0
            state["totalStudiedSeconds"] = int(ts)
        except Exception:
            state["completionPercent"] = 0.0
            state["studiedCardsCount"] = 0
            state["totalStudiedSeconds"] = 0
        state["difficult"] = difficult_cards(
            mid, sel, get_selected_deck_id(), word_field_index=get_word_field_index()
        )
        from .data_access import template_status_counts
        state["status"] = template_status_counts(mid, sel, get_selected_deck_id())
    else:
        state.update(
            {
                "progress": {"labels": [], "series": []},
                "learningHistory": {"labels": [], "series": []},
                "timeSpent": {"binSize":15, "labels": [], "histograms": {}, "top": {}},
                "timeStudied": {"labels": [], "series": []},
                "difficult": {"byTemplate": {}},
                "status": {"byTemplate": {}},
                "completionPercent": 0.0,
                "studiedCardsCount": 0,
                "totalStudiedSeconds": 0,
            }
        )
    return json.dumps(state)


def load_web_content(dialog: QDialog) -> None:
    web: AnkiWebView = dialog._web  # type: ignore[attr-defined]
    addon_dir = Path(__file__).resolve().parent
    index_path = addon_dir / "web" / "index.html"
    if not index_path.exists():
        showInfo(f"Missing index.html for {ADDON_NAME}")
        return
    mw.addonManager.setWebExports(ADDON_MODULE, r"web/.*")
    html = index_path.read_text(encoding="utf-8")
    pkg = mw.addonManager.addonFromModule(ADDON_MODULE)
    html = html.replace('href="app.css"', f'href="/_addons/{pkg}/web/app.css"')
    html = html.replace('src="app.js"', f'src="/_addons/{pkg}/web/app.js"')
    web.stdHtml(html, context=None)
    inject_dynamic_state(web)


def inject_dynamic_state(web: AnkiWebView) -> None:
    js = f"deckcompletionstatsUpdateState({json.dumps(build_state_json())});"
    web.eval(js)


def refresh_web(dialog: QDialog) -> None:
    web: AnkiWebView = dialog._web  # type: ignore[attr-defined]
    inject_dynamic_state(web)


# Bridge handling -----------------------------------------------------------


def on_js_message(handled: Tuple[bool, Optional[str]], message: str, context):  # type: ignore[override]
    if message == "deckcompletionstats_refresh":
        dlg = getattr(mw, "deckcompletionstats_dialog", None)
        refresh_web(dlg) if dlg else None
        return (True, None)
    if message == "deckcompletionstats_select_deck":
        choose_deck()
        dlg = getattr(mw, "deckcompletionstats_dialog", None)
        refresh_web(dlg) if dlg else None
        return (True, None)
    if message == "deckcompletionstats_select_model":
        choose_model()
        dlg = getattr(mw, "deckcompletionstats_dialog", None)
        refresh_web(dlg) if dlg else None
        return (True, None)
    if message == "deckcompletionstats_select_word_field":
        choose_word_field()
        dlg = getattr(mw, "deckcompletionstats_dialog", None)
        refresh_web(dlg) if dlg else None
        return (True, None)
    if message.startswith("deckcompletionstats_update_templates:"):
        payload = message.split(":", 1)[1]
        try:
            ords = json.loads(payload)
            if isinstance(ords, list):
                set_selected_template_ords([int(o) for o in ords])
        except Exception:
            pass
        dlg = getattr(mw, "deckcompletionstats_dialog", None)
        refresh_web(dlg) if dlg else None
        return (True, None)
    if message.startswith("deckcompletionstats_set_granularity:"):
        g = message.split(":", 1)[1]
        set_granularity(g)
        dlg = getattr(mw, "deckcompletionstats_dialog", None)
        refresh_web(dlg) if dlg else None
        return (True, None)
    if message.startswith("deckcompletionstats_set_forecast:"):
        flag = message.split(":", 1)[1]
        set_forecast_enabled(flag == "1")
        dlg = getattr(mw, "deckcompletionstats_dialog", None)
        refresh_web(dlg) if dlg else None
        return (True, None)
    return handled


# Selection dialogs ---------------------------------------------------------


def choose_deck() -> None:
    if not mw.col:
        return
    decks = list_decks()
    decks_sorted = sorted(decks, key=lambda x: x[1].lower())
    names = ["All Decks"] + [name for _, name in decks_sorted]
    current_name = selected_deck_name()
    current_index = 0
    if current_name != "All Decks":
        for i, (_, name) in enumerate(decks_sorted, start=1):
            if name == current_name:
                current_index = i
                break
    name, ok = QInputDialog.getItem(
        mw, ADDON_NAME, "Select deck scope:", names, current_index, False
    )
    if not ok:
        return
    chosen_deck_id: Optional[int] = None
    if name == "All Decks":
        set_selected_deck_id(None)
        set_selected_model_id(None)
    else:
        for did, dname in decks_sorted:
            if dname == name:
                set_selected_deck_id(did)
                chosen_deck_id = did
                break
    if chosen_deck_id is not None and mw.col:
        deck_obj = mw.col.decks.get(cast(DeckId, chosen_deck_id))
        if deck_obj:
            deck_name = deck_obj["name"].replace('"', '"')
            cids = mw.col.find_cards(f'deck:"{deck_name}"')
            if cids:
                card = mw.col.get_card(cids[0])
                try:
                    note = card.note()
                    mid = getattr(note, "mid", None)
                    if mid is None:
                        nt = getattr(note, "note_type", lambda: None)()
                        mid = nt.get("id") if nt else None
                    if mid is not None:
                        set_selected_model_id(mid)
                except Exception:
                    pass
            else:
                set_selected_model_id(None)


def choose_model() -> None:
    if not mw.col:
        return
    models = list_models()
    model_pairs = [(m.get("id"), m.get("name", "(Unnamed)"), m) for m in models]
    model_pairs_sorted = sorted(model_pairs, key=lambda x: x[1].lower())
    names = [name for _, name, _ in model_pairs_sorted]
    current_mid = get_selected_model_id()
    current_index = 0
    if current_mid is not None:
        for i, (mid, nm, _) in enumerate(model_pairs_sorted, start=1):
            if mid == current_mid:
                current_index = i
                break
    sel, ok = QInputDialog.getItem(
        mw, ADDON_NAME, "Select model:", names, current_index, False
    )
    if not ok:
        return
    chosen_model = None
    for mid, nm, m in model_pairs_sorted:
        if nm == sel:
            chosen_model = m
            set_selected_model_id(mid)
            break
    if not chosen_model:
        return
    fields = [f for f in chosen_model.get("flds", [])]
    field_names = [f.get("name", "") for f in fields]
    if field_names:
        default_idx = min(get_word_field_index(), len(field_names) - 1)
        word_field_name, ok_w = QInputDialog.getItem(
            mw, ADDON_NAME, "Select Word Field:", field_names, default_idx, False
        )
        if ok_w and word_field_name in field_names:
            set_word_field_index(field_names.index(word_field_name))
    dlg = getattr(mw, "deckcompletionstats_dialog", None)
    refresh_web(dlg) if dlg else None


def choose_word_field() -> None:
    mid = get_selected_model_id()
    if mid is None:
        showInfo("Select a model first.")
        return
    mdl = next((m for m in list_models() if m.get("id") == mid), None)
    if not mdl:
        showInfo("Model not found.")
        return
    fields = [f for f in mdl.get("flds", [])]
    field_names = [f.get("name", "") for f in fields]
    if not field_names:
        showInfo("No fields in model.")
        return
    default_idx = min(get_word_field_index(), len(field_names) - 1)
    word_field_name, ok_w = QInputDialog.getItem(
        mw, ADDON_NAME, "Select Word Field:", field_names, default_idx, False
    )
    if ok_w and word_field_name in field_names:
        set_word_field_index(field_names.index(word_field_name))


# Register hook -------------------------------------------------------------
if not getattr(gui_hooks, "_deckcompletionstats_registered", False):  # type: ignore[attr-defined]
    gui_hooks.webview_did_receive_js_message.append(on_js_message)
    gui_hooks._deckcompletionstats_registered = True  # type: ignore[attr-defined]

# Menu action ---------------------------------------------------------------
action = QAction(ADDON_NAME, mw)
qconnect(action.triggered, show_statistics_window)
mw.form.menuTools.addAction(action)
