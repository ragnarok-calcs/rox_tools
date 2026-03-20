"""
db.py
-----
MongoDB Atlas connection and per-user build persistence.

Two collections:
  - `builds`      Global store; one document per build, keyed by UUID.
  - `user_builds` Per-user index; maps user_key (SHA-256 hash) → {name: uuid}.

The MongoClient is cached via @st.cache_resource so the connection is
reused across Streamlit reruns rather than re-opened each time.
"""

import uuid
import datetime
import streamlit as st
from pymongo import MongoClient


@st.cache_resource
def _get_db():
    client = MongoClient(st.secrets["MONGO_URI"], serverSelectionTimeoutMS=5000)
    return client["rox"]


def _builds_col():
    return _get_db()["builds"]


def _user_col():
    return _get_db()["user_builds"]


def ensure_indexes() -> None:
    """Create unique indexes on both collections. Idempotent — safe to call on every startup."""
    _builds_col().create_index([("build_id", 1)], unique=True)
    _user_col().create_index([("user_key", 1)],   unique=True)


# ---------------------------------------------------------------------------
# Global builds collection
# ---------------------------------------------------------------------------

def upsert_build(build_id: str, name: str,
                 offensive: dict, defensive: dict, weapon_meta: dict) -> None:
    """Upsert a build document into the global builds collection."""
    now = datetime.datetime.utcnow()
    _builds_col().update_one(
        {"build_id": build_id},
        {
            "$set": {
                "canonical_name": name,
                "offensive":      offensive,
                "defensive":      defensive,
                "weapon_meta":    weapon_meta,
                "updated_at":     now,
            },
            "$setOnInsert": {"created_at": now},
        },
        upsert=True,
    )


def fetch_builds_by_ids(build_ids: list) -> dict:
    """Batch-fetch builds from the global collection. Returns {build_id: doc}."""
    if not build_ids:
        return {}
    docs = _builds_col().find({"build_id": {"$in": build_ids}}, {"_id": 0})
    return {d["build_id"]: d for d in docs}


# ---------------------------------------------------------------------------
# User index collection
# ---------------------------------------------------------------------------

def _save_user_index(user_key: str, build_index: dict) -> None:
    """Upsert the user's {display_name: build_id} index."""
    _user_col().update_one(
        {"user_key": user_key},
        {"$set": {"build_index": build_index,
                  "updated_at":  datetime.datetime.utcnow()}},
        upsert=True,
    )


# ---------------------------------------------------------------------------
# Assembled session-state dict helper
# ---------------------------------------------------------------------------

def _assemble(build_index: dict, fetched: dict) -> dict:
    """
    Convert a user's build index + fetched global docs into the session-state
    shape: {display_name: {build_id, offensive, defensive, weapon_meta}}.
    Silently skips any build_id not found in the global collection.
    """
    result = {}
    for display_name, bid in build_index.items():
        doc = fetched.get(bid)
        if doc:
            result[display_name] = {
                "build_id":    bid,
                "offensive":   doc.get("offensive",  {}),
                "defensive":   doc.get("defensive",  {}),
                "weapon_meta": doc.get("weapon_meta", {}),
            }
    return result


# ---------------------------------------------------------------------------
# Primary load / save entry points (called by build_store.py)
# ---------------------------------------------------------------------------

def load_builds_for_user(user_key: str) -> dict:
    """
    Load all builds for a user, returning the session-state-shaped dict.
    Auto-migrates the old single-collection format on first call:
      Old: {user_email: hash, builds: {name: {offensive, defensive, weapon_meta}}}
      New: {user_key: hash, build_index: {name: uuid}}
    """
    doc = _user_col().find_one({"user_key": user_key}, {"_id": 0})

    # Check for old format stored under "user_email" field (pre-migration field name)
    if doc is None:
        old = _user_col().find_one({"user_email": user_key}, {"_id": 0})
        if old and "builds" in old and "build_index" not in old:
            doc = old  # fall through to migration block below

    # Migrate old embedded-builds format → two-collection format
    if doc is not None and "builds" in doc and "build_index" not in doc:
        build_index: dict = {}
        for name, data in doc["builds"].items():
            bid = str(uuid.uuid4())
            upsert_build(bid, name,
                         data.get("offensive",  {}),
                         data.get("defensive",  {}),
                         data.get("weapon_meta", {}))
            build_index[name] = bid
        _user_col().update_one(
            {"user_key": user_key},
            {
                "$set":   {"build_index": build_index,
                           "user_key":    user_key,
                           "updated_at":  datetime.datetime.utcnow()},
                "$unset": {"builds": "", "user_email": ""},
            },
            upsert=True,
        )
        return _assemble(build_index, fetch_builds_by_ids(list(build_index.values())))

    if not doc or "build_index" not in doc:
        return {}

    build_index = doc["build_index"]
    return _assemble(build_index, fetch_builds_by_ids(list(build_index.values())))


def save_builds_for_user(user_key: str, builds: dict) -> None:
    """
    Persist all builds for a user.
    Upserts each build into the global collection, then rewrites the user index.
    builds format: {display_name: {build_id, offensive, defensive, weapon_meta}}
    """
    build_index: dict = {}
    for display_name, entry in builds.items():
        bid = entry.get("build_id")
        if not bid:
            continue
        upsert_build(bid, display_name,
                     entry.get("offensive",  {}),
                     entry.get("defensive",  {}),
                     entry.get("weapon_meta", {}))
        build_index[display_name] = bid
    _save_user_index(user_key, build_index)
