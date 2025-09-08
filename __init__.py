# Deck Completion Stats Add-on

"""
Adds a Tools menu item to open a window with deck completion statistics.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Optional, Tuple, cast

from anki.decks import DeckId
from aqt import gui_hooks, mw
from aqt.qt import QAction, QDialog, QInputDialog, QVBoxLayout
from aqt.utils import qconnect, showInfo
from aqt.webview import AnkiWebView

from . import config
from .analytics import (
    difficult_cards,
    learning_history,
    streak_days,
    time_spent_stats,
    time_studied_history,
)
from .data_access import (
    all_model_templates,
    deck_card_count,
    list_decks,
    list_models,
    model_name,
    model_templates,
    template_progress,
    template_status_counts,
)
from .utils import parse_flexible_date

ADDON_NAME = "Deck Completion Stats"
ADDON_MODULE = __name__.split(".")[0]


def selected_deck_name() -> str:
    """Gets the name of the currently selected deck from config."""
    did = config.get_selected_deck_id()
    if did is None:
        return "(All Decks)"
    try:
        deck = mw.col.decks.get(cast(DeckId, did))
        if not deck:
            config.set_selected_deck_id(None)
            return "(All Decks)"
        return deck["name"]
    except Exception:
        config.set_selected_deck_id(None)
        return "(All Decks)"


#
# UI-related functions
#


def show_statistics_window() -> None:
    """Create and show the main statistics window."""
    if not mw.col:
        showInfo("Please open a collection first.")
        return

    # Reuse existing window if available
    existing = getattr(mw, "deckcompletionstats_dialog", None)
    if existing and existing.isVisible():
        refresh_web(existing)
        existing.raise_()
        existing.activateWindow()
        return

    # Create a new window
    dialog = QDialog(mw)
    dialog.setWindowTitle(ADDON_NAME)
    dialog.setModal(False)
    layout = QVBoxLayout(dialog)
    web = AnkiWebView(dialog)
    layout.addWidget(web)
    dialog.resize(1200, 800)

    # Keep references to avoid garbage collection
    dialog._web = web  # type: ignore[attr-defined]
    mw.deckcompletionstats_dialog = dialog  # type: ignore[attr-defined]

    load_web_content(dialog)
    dialog.show()


def build_state_json() -> str:
    """
    Gathers all necessary data from backend modules and serializes it into a
    JSON string for the webview.
    """
    state: dict[str, Any] = {
        "count": deck_card_count(config.get_selected_deck_id()),
        "deckName": selected_deck_name(),
        "modelName": model_name(config.get_selected_model_id()),
        "granularity": config.get_granularity(),
        "streak": streak_days(config.get_selected_deck_id()),
        "dateFilterStart": config.get_date_filter_start(),
        "dateFilterEnd": config.get_date_filter_end(),
    }

    mid = config.get_selected_model_id()
    if mid is not None:
        sel_ords = config.get_selected_template_ords()
        deck_id = config.get_selected_deck_id()
        granularity = config.get_granularity()

        # Core data from analytics and data_access modules
        state.update(
            {
                "templates": [
                    {
                        "ord": t.get("ord"),
                        "name": t.get("name") or f"Card {t.get('ord', 0) + 1}",
                    }
                    for t in model_templates(mid)
                ],
                "selectedTemplates": sel_ords,
                "progress": template_progress(
                    mid,
                    sel_ords,
                    deck_id,
                    granularity,
                    forecast=config.is_forecast_enabled(),
                ),
                "forecastEnabled": config.is_forecast_enabled(),
                "learningHistory": learning_history(mid, sel_ords, deck_id, granularity),
                "timeSpent": time_spent_stats(mid, sel_ords, deck_id),
                "timeStudied": time_studied_history(mid, sel_ords, deck_id, granularity),
                "difficult": difficult_cards(mid, sel_ords, deck_id),
                "status": template_status_counts(mid, sel_ords, deck_id),
            }
        )

        # Add field names for difficult card display
        try:
            mdl = next((m for m in list_models() if m.get("id") == mid), None)
            if mdl:
                state["fieldNames"] = [f.get("name", "") for f in mdl.get("flds", [])]
        except Exception:
            state["fieldNames"] = []

        # Derived high-level metrics for dashboard KPIs
        try:
            progress_series = state.get("progress", {}).get("series", []) or []
            studied_sum = sum(
                s.get("data", [])[-1] for s in progress_series if s.get("data")
            )
            total_sum = sum(s.get("totalCards", 0) for s in progress_series)

            state["completionPercent"] = (
                round(studied_sum / total_sum * 100, 1) if total_sum > 0 else 0.0
            )
            state["studiedCardsCount"] = studied_sum
            state["totalStudiedSeconds"] = int(
                state.get("timeStudied", {}).get("totalSecondsAll", 0)
            )
        except (IndexError, TypeError, ZeroDivisionError):
            state["completionPercent"] = 0.0
            state["studiedCardsCount"] = 0
            state["totalStudiedSeconds"] = 0

    else:
        # Handle "Any Model" case - get templates from all models
        deck_id = config.get_selected_deck_id()
        granularity = config.get_granularity()

        # For "Any Model", we don't use template selection filtering
        # because templates from different models can have conflicting ordinals
        all_templates_list = all_model_templates(deck_id)
        
        # Core data from analytics and data_access modules
        state.update(
            {
                "templates": [
                    {
                        "ord": t.get("ord"),
                        "name": t.get("full_name") or f"Card {t.get('ord', 0) + 1}",
                        "model_id": t.get("model_id"),
                        "model_name": t.get("model_name"),
                    }
                    for t in all_templates_list
                ],
                "selectedTemplates": [],  # No template filtering for "Any Model"
                "progress": template_progress(
                    None,  # model_id = None for all models
                    None,  # template_ords = None for all templates
                    deck_id,
                    granularity,
                    forecast=config.is_forecast_enabled(),
                ),
                "forecastEnabled": config.is_forecast_enabled(),
                "learningHistory": learning_history(None, None, deck_id, granularity),
                "timeSpent": time_spent_stats(None, None, deck_id),
                "timeStudied": time_studied_history(None, None, deck_id, granularity),
                "difficult": difficult_cards(None, None, deck_id),
                "status": template_status_counts(None, None, deck_id),
            }
        )

        # For "Any Model", we can't provide specific field names since they vary by model
        state["fieldNames"] = []

        # Derived high-level metrics for dashboard KPIs
        try:
            progress_series = state.get("progress", {}).get("series", []) or []
            studied_sum = sum(
                s.get("data", [])[-1] for s in progress_series if s.get("data")
            )
            total_sum = sum(s.get("totalCards", 0) for s in progress_series)

            state["completionPercent"] = (
                round(studied_sum / total_sum * 100, 1) if total_sum > 0 else 0.0
            )
            state["studiedCardsCount"] = studied_sum
            state["totalStudiedSeconds"] = int(
                state.get("timeStudied", {}).get("totalSecondsAll", 0)
            )
        except (IndexError, TypeError, ZeroDivisionError):
            state["completionPercent"] = 0.0
            state["studiedCardsCount"] = 0
            state["totalStudiedSeconds"] = 0
    return json.dumps(state)


def load_web_content(dialog: QDialog) -> None:
    """Loads the initial HTML and injects the dynamic state."""
    # Check if both All Decks and Any Model are selected - this combination
    # can cause the app to freeze for minutes due to massive data loading
    if config.get_selected_deck_id() is None and config.get_selected_model_id() is None:
        # Show deck selection prompt immediately before any data loading
        choose_deck_on_startup()
        # After deck selection, check again - if user cancelled, close dialog
        if config.get_selected_deck_id() is None:
            dialog.close()
            return
    
    web: AnkiWebView = dialog._web  # type: ignore[attr-defined]
    addon_dir = Path(__file__).resolve().parent
    index_path = addon_dir / "web" / "index.html"

    if not index_path.exists():
        showInfo(f"Missing required file: {index_path}")
        return

    # Set up web exports for CSS/JS
    mw.addonManager.setWebExports(ADDON_MODULE, r"web/.*")
    pkg = mw.addonManager.addonFromModule(ADDON_MODULE)

    html = index_path.read_text(encoding="utf-8")
    # Replace relative paths with absolute paths to addon resources
    html = html.replace('href="app.css"', f'href="/_addons/{pkg}/web/app.css"')
    html = html.replace('src="app.js"', f'src="/_addons/{pkg}/web/app.js"')

    web.stdHtml(html, context=None)
    inject_dynamic_state(web)


def inject_dynamic_state(web: AnkiWebView) -> None:
    """Serializes the current state and sends it to the webview."""
    js = f"deckcompletionstatsUpdateState({json.dumps(build_state_json())});"
    web.eval(js)


def refresh_web(dialog: QDialog) -> None:
    """Just injects the latest state into the existing webview."""
    web: AnkiWebView = dialog._web  # type: ignore[attr-defined]
    inject_dynamic_state(web)


#
# Bridge handling for messages from Javascript
#


def on_js_message(
    handled: Tuple[bool, Any], message: str, context: Any
) -> Tuple[bool, Any]:
    """
    Handles messages sent from the webview's Javascript.
    The message format is "deckcompletionstats_COMMAND:PAYLOAD".
    """
    if not message.startswith("deckcompletionstats_"):
        return handled

    dlg = getattr(mw, "deckcompletionstats_dialog", None)
    command, *payload = message.split(":", 1)
    payload_str = payload[0] if payload else ""

    if command == "deckcompletionstats_select_deck":
        choose_deck()
    elif command == "deckcompletionstats_select_model":
        choose_model()
    elif command == "deckcompletionstats_update_templates":
        try:
            ords = json.loads(payload_str)
            if isinstance(ords, list):
                config.set_selected_template_ords([int(o) for o in ords])
        except (IndexError, json.JSONDecodeError):
            pass  # Ignore malformed messages
    elif command == "deckcompletionstats_set_granularity":
        if payload_str:
            config.set_granularity(payload_str)
    elif command == "deckcompletionstats_set_forecast":
        if payload_str:
            config.set_forecast_enabled(payload_str == "1")
    elif command == "deckcompletionstats_set_date_filters":
        try:
            date_filters = json.loads(payload_str)
            if isinstance(date_filters, dict):
                start_date = date_filters.get("start") or None
                end_date = date_filters.get("end") or None
                
                # Handle flexible date parsing
                if start_date:
                    start_date = parse_flexible_date(start_date, default_to_start=True)
                if end_date:
                    end_date = parse_flexible_date(end_date, default_to_start=False)
                
                config.set_date_filter_start(start_date)
                config.set_date_filter_end(end_date)
        except (json.JSONDecodeError, TypeError):
            pass  # Ignore malformed messages

    # Refresh the webview after any action
    if dlg:
        refresh_web(dlg)

    return (True, None)


#
# User selection dialogs
#


def choose_deck() -> None:
    """Shows a dialog to let the user select a deck."""
    if not mw.col:
        return

    decks = sorted(list_decks(), key=lambda x: x[1].lower())
    names = ["(All Decks)"] + [name for _, name in decks]
    current_name = selected_deck_name()
    current_index = names.index(current_name) if current_name in names else 0

    name, ok = QInputDialog.getItem(
        mw, ADDON_NAME, "Select deck scope:", names, current_index, False
    )
    if not ok:
        return

    if name == "(All Decks)":
        config.set_selected_deck_id(None)
        config.set_selected_model_id(None)
    else:
        # Find the deck ID from the selected name
        chosen_deck_id = next((did for did, dname in decks if dname == name), None)
        if chosen_deck_id:
            config.set_selected_deck_id(chosen_deck_id)


def choose_model() -> None:
    """Shows a dialog to let the user select a notetype (model)."""
    if not mw.col:
        return

    models = sorted(
        [(m.get("id"), m.get("name", "(Unnamed)")) for m in list_models()],
        key=lambda x: x[1].lower(),
    )
    names = ["(Any Model)"] + [name for _, name in models]
    current_mid = config.get_selected_model_id()
    current_name = next(
        (name for mid, name in models if mid == current_mid), "(Any Model)"
    )
    current_index = names.index(current_name) if current_name in names else 0

    sel, ok = QInputDialog.getItem(
        mw, ADDON_NAME, "Select model:", names, current_index, False
    )
    if not ok:
        return

    if sel == "(Any Model)":
        config.set_selected_model_id(None)
    else:
        chosen_model_id = next((mid for mid, name in models if name == sel), None)
        if chosen_model_id:
            config.set_selected_model_id(chosen_model_id)

    # No need to manually refresh here, on_js_message handles it


def choose_deck_on_startup() -> None:
    """Shows a startup dialog to let the user select a specific deck to avoid performance issues."""
    if not mw.col:
        return
    
    decks = sorted(list_decks(), key=lambda x: x[1].lower())
    names = [name for _, name in decks]  # Don't include "(All Decks)" option
    
    if not names:
        # No decks available
        showInfo("No decks found in your collection.", title=ADDON_NAME)
        return

    name, ok = QInputDialog.getItem(
        mw, ADDON_NAME, "Select a deck to analyze:", names, 0, False
    )
    if not ok:
        return

    # Find the deck ID from the selected name
    chosen_deck_id = next((did for did, dname in decks if dname == name), None)
    if chosen_deck_id:
        config.set_selected_deck_id(chosen_deck_id)


#
# Add-on setup
#

def setup() -> None:
    """Registers hooks and adds the menu item."""
    # Register the JS message handler
    gui_hooks.webview_did_receive_js_message.append(on_js_message)

    # Add menu item
    action = QAction(ADDON_NAME, mw)
    qconnect(action.triggered, show_statistics_window)
    mw.form.menuTools.addAction(action)

# Run setup
setup()

ADDON_NAME = "Deck Completion Stats"
ADDON_MODULE = __name__.split(".")[0]
