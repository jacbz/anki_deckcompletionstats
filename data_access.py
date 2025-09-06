from __future__ import annotations
"""Data access utilities for Statistics 5000.

All direct interaction with Anki collection objects that provides data to the UI
should reside here to keep the main __init__ lean.
"""
from typing import Optional, List, Dict, Any
from aqt import mw


def deck_card_count(deck_id: Optional[int]) -> int:
    if not mw.col:
        return 0
    if deck_id is None:
        return mw.col.card_count()
    deck = mw.col.decks.get(deck_id)
    if not deck:
        return mw.col.card_count()
    deck_name = deck["name"].replace('"', '\"')
    query = f'deck:"{deck_name}"'
    return len(mw.col.find_cards(query))


def list_decks() -> list[tuple[int, str]]:
    if not mw.col:
        return []
    try:
        return [(d.id, d.name) for d in mw.col.decks.all_names_and_ids()]
    except Exception:
        # fallback shape
        out: list[tuple[int, str]] = []
        for d in mw.col.decks.all_names_and_ids():  # type: ignore
            did = getattr(d, 'id', None) or getattr(d, 'did', None)
            name = getattr(d, 'name', None)
            if did is not None and name is not None:
                out.append((did, name))
        return out


def list_models() -> list[dict[str, Any]]:
    if not mw.col:
        return []
    return mw.col.models.all()  # type: ignore[return-value]


def get_model(model_id: int) -> Optional[dict[str, Any]]:
    if not mw.col:
        return None
    return mw.col.models.get(model_id)  # type: ignore[return-value]


def model_templates(model_id: int) -> list[dict[str, Any]]:
    m = get_model(model_id)
    if not m:
        return []
    # Modern Anki: templates under 'tmpls'
    return m.get('tmpls', [])  # type: ignore[return-value]


def model_name(model_id: Optional[int]) -> str:
    if model_id is None:
        return "(Any Model)"
    m = get_model(model_id)
    if not m:
        return "(Missing Model)"
    return m.get('name', '(Unnamed Model)')
