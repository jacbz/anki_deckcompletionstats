"""Configuration management for the Deck Completion Stats add-on."""
from __future__ import annotations

from typing import Any, Optional

from aqt import mw

ADDON_MODULE = __name__.split(".")[0]


def get_config() -> dict[str, Any]:
    """
    Retrieves the add-on's configuration dictionary, ensuring default values for all keys.

    Returns:
        A dictionary containing the add-on's configuration.
    """
    cfg = mw.addonManager.getConfig(ADDON_MODULE) or {}
    cfg.setdefault("selected_deck_id", None)
    cfg.setdefault("selected_model_id", None)
    cfg.setdefault("selected_model_templates", None)
    cfg.setdefault("granularity", "days")
    cfg.setdefault("progress_forecast_enabled", False)
    return cfg


def set_config(cfg: dict[str, Any]) -> None:
    """
    Writes the provided configuration dictionary to the add-on's config file.

    Args:
        cfg: The configuration dictionary to save.
    """
    mw.addonManager.writeConfig(ADDON_MODULE, cfg)


def get_selected_deck_id() -> Optional[int]:
    """
    Gets the ID of the currently selected deck from the configuration.

    Returns:
        The deck ID, or None if no deck is selected.
    """
    return get_config().get("selected_deck_id")


def set_selected_deck_id(did: Optional[int]) -> None:
    """
    Sets the ID of the selected deck in the configuration.

    Args:
        did: The deck ID to store.
    """
    cfg = get_config()
    cfg["selected_deck_id"] = did
    set_config(cfg)


def get_selected_model_id() -> Optional[int]:
    """
    Gets the ID of the currently selected notetype (model) from the configuration.

    Returns:
        The notetype ID, or None if no notetype is selected.
    """
    return get_config().get("selected_model_id")


def set_selected_model_id(mid: Optional[int]) -> None:
    """
    Sets the ID of the selected notetype (model) in the configuration.
    Also resets the selected templates.

    Args:
        mid: The notetype ID to store.
    """
    cfg = get_config()
    cfg["selected_model_id"] = mid
    cfg["selected_model_templates"] = None
    set_config(cfg)


def get_selected_template_ords() -> Optional[list[int]]:
    """
    Gets the list of selected template ordinals for the current notetype.

    Returns:
        A list of integer ordinals, or None if no templates are selected.
    """
    return get_config().get("selected_model_templates")


def set_selected_template_ords(ords: Optional[list[int]]) -> None:
    """
    Sets the list of selected template ordinals in the configuration.

    Args:
        ords: A list of integer ordinals.
    """
    cfg = get_config()
    cfg["selected_model_templates"] = ords
    set_config(cfg)


def get_granularity() -> str:
    """
    Gets the time granularity for statistics from the configuration.

    Returns:
        A string representing the granularity (e.g., "days", "weeks").
    """
    return get_config().get("granularity", "days")


def set_granularity(g: str) -> None:
    """
    Sets the time granularity for statistics in the configuration.

    Args:
        g: The granularity string to store.
    """
    cfg = get_config()
    cfg["granularity"] = g
    set_config(cfg)


def is_forecast_enabled() -> bool:
    """
    Checks if the progress forecast feature is enabled in the configuration.

    Returns:
        True if forecasting is enabled, False otherwise.
    """
    return bool(get_config().get("progress_forecast_enabled", False))


def set_forecast_enabled(on: bool) -> None:
    """
    Enables or disables the progress forecast feature in the configuration.

    Args:
        on: True to enable, False to disable.
    """
    cfg = get_config()
    cfg["progress_forecast_enabled"] = on
    set_config(cfg)
