"""Bulk team import from CSV or JSON text."""
from __future__ import annotations

import csv
import io
import json
from typing import Any

from config import DIVISIONS
from rules import division_has_captain_role, roster_labels
from state import find_team_by_name, find_team_by_user, new_team_id, normalize_division


def parse_import_payload(text: str) -> list[dict[str, str]]:
    """
    Accept:
      - JSON array of objects
      - CSV with header: team_name,division,captain_id,teammate_id
    Classic/Arcade need both IDs. Fusion may be solo (1v1) with captain only.
    """
    raw = (text or "").strip()
    if not raw:
        return []
    if raw.startswith("["):
        data = json.loads(raw)
        if not isinstance(data, list):
            raise ValueError("JSON must be an array of teams")
        rows = []
        for item in data:
            if not isinstance(item, dict):
                continue
            rows.append({str(k).lower(): str(v).strip() for k, v in item.items() if v is not None})
        return rows

    f = io.StringIO(raw)
    sample = raw[:200]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",\t;")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(f, dialect=dialect)
    rows = []
    for row in reader:
        rows.append({(k or "").strip().lower(): (v or "").strip() for k, v in row.items()})
    return rows


def _pick(row: dict[str, str], *keys: str) -> str:
    for k in keys:
        if k in row and row[k]:
            return row[k]
    return ""


def _strip_mention(val: str) -> str:
    v = (val or "").strip()
    if v.startswith("<@") and v.endswith(">"):
        v = v[2:-1].lstrip("!")
    return v


def import_teams(state: dict[str, Any], text: str) -> tuple[list[str], list[str]]:
    """Returns (ok_lines, error_lines). Mutates state teams list; caller saves."""
    rows = parse_import_payload(text)
    ok: list[str] = []
    err: list[str] = []
    for i, row in enumerate(rows, start=1):
        name = _pick(row, "team_name", "name", "team")
        div_raw = _pick(row, "division", "div")
        cap = _strip_mention(
            _pick(
                row,
                "captain_id",
                "captain_discord_id",
                "captain",
                "captain_user_id",
                "captain_a_id",
                "captain_a",
                "player1_id",
                "player1",
            )
        )
        mate = _strip_mention(
            _pick(
                row,
                "teammate_id",
                "teammate_discord_id",
                "teammate",
                "teammate_user_id",
                "captain_b_id",
                "captain_b",
                "player2_id",
                "player2",
            )
        )

        if not name or not div_raw or not cap:
            err.append(f"Row {i}: need team_name, division, captain_id")
            continue
        div = normalize_division(div_raw)
        if not div:
            err.append(f"Row {i} ({name}): bad division (use {', '.join(DIVISIONS)})")
            continue

        slot1, slot2 = roster_labels(div)
        fusion_solo = div == "fusion" and not mate

        if not cap.isdigit():
            err.append(f"Row {i} ({name}): captain ID must be Discord user ID")
            continue
        if not fusion_solo:
            if not mate or not mate.isdigit():
                err.append(f"Row {i} ({name}): need both player IDs for {div}")
                continue
            if cap == mate:
                err.append(f"Row {i} ({name}): {slot1} and {slot2} must differ")
                continue
        if find_team_by_name(state, name):
            err.append(f"Row {i} ({name}): team name already exists")
            continue
        if find_team_by_user(state, int(cap)):
            err.append(f"Row {i} ({name}): {slot1} already on a team")
            continue
        if mate and mate.isdigit() and find_team_by_user(state, int(mate)):
            err.append(f"Row {i} ({name}): {slot2} already on a team")
            continue
        team = {
            "id": new_team_id(),
            "name": name.strip(),
            "division": div,
            "captain_user_id": str(int(cap)),
            "teammate_user_id": str(int(mate)) if mate and mate.isdigit() else None,
            "active": True,
        }
        state.setdefault("teams", []).append(team)
        if fusion_solo:
            ok.append(f"**{team['name']}** ({div}, solo) `{team['id']}`")
        elif not division_has_captain_role(div):
            ok.append(f"**{team['name']}** ({div}, both captains) `{team['id']}`")
        else:
            ok.append(f"**{team['name']}** ({div}) `{team['id']}`")
    return ok, err
