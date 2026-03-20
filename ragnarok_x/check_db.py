"""
check_db.py
-----------
Standalone diagnostic script for the MongoDB Atlas connection.
Run from the ragnarok_x/ directory:

    python check_db.py

Does NOT require a running Streamlit server.  Reads MONGO_URI directly from
.streamlit/secrets.toml, then checks connectivity, lists collection contents,
and performs a write → read → delete round-trip.
"""

import sys
import os
import json
import uuid
import datetime

# ── 1. Load MONGO_URI from secrets.toml ──────────────────────────────────────
secrets_path = os.path.join(os.path.dirname(__file__), ".streamlit", "secrets.toml")

if not os.path.exists(secrets_path):
    print(f"[ERROR] secrets.toml not found at: {secrets_path}")
    sys.exit(1)

try:
    if sys.version_info >= (3, 11):
        import tomllib
        with open(secrets_path, "rb") as f:
            secrets = tomllib.load(f)
    else:
        try:
            import tomli as tomllib        # pip install tomli
            with open(secrets_path, "rb") as f:
                secrets = tomllib.load(f)
        except ImportError:
            import toml                    # pip install toml (fallback)
            with open(secrets_path) as f:
                secrets = toml.load(f)
except Exception as e:
    print(f"[ERROR] Could not parse secrets.toml: {e}")
    sys.exit(1)

mongo_uri = secrets.get("MONGO_URI")
if not mongo_uri:
    print("[ERROR] MONGO_URI not found in secrets.toml")
    sys.exit(1)

_host = mongo_uri.split("@")[-1].split("/")[0] if "@" in mongo_uri else "(no host parsed)"
print(f"[OK]  MONGO_URI found  (host: {_host})")

# ── 2. Connect ────────────────────────────────────────────────────────────────
try:
    from pymongo import MongoClient
    from pymongo.errors import ServerSelectionTimeoutError, OperationFailure
except ImportError:
    print("[ERROR] pymongo is not installed.  Run: pip install 'pymongo[srv]>=4.6'")
    sys.exit(1)

print("      Connecting (timeout 8 s)…")
try:
    client = MongoClient(mongo_uri, serverSelectionTimeoutMS=8000)
    # Force an actual round-trip to verify connectivity
    client.admin.command("ping")
    print("[OK]  Connected to MongoDB Atlas")
except ServerSelectionTimeoutError as e:
    print(f"[FAIL] Cannot reach MongoDB Atlas — check network / Atlas IP allow-list.\n       {e}")
    sys.exit(1)
except Exception as e:
    print(f"[FAIL] Connection error: {e}")
    sys.exit(1)

db = client["rox"]
builds_col   = db["builds"]
user_col     = db["user_builds"]

# ── 3. Collection counts ──────────────────────────────────────────────────────
try:
    n_builds = builds_col.count_documents({})
    n_users  = user_col.count_documents({})
    print(f"\n── Collection sizes ───────────────────────────────────")
    print(f"   builds      : {n_builds} document(s)")
    print(f"   user_builds : {n_users} document(s)")
except OperationFailure as e:
    print(f"[FAIL] Permission error reading collections: {e}")
    sys.exit(1)

# ── 4. Sample documents ───────────────────────────────────────────────────────
print(f"\n── builds (up to 5) ────────────────────────────────────")
for doc in builds_col.find({}, {"_id": 0, "offensive": 0, "defensive": 0, "weapon_meta": 0}).limit(5):
    print(f"   {json.dumps(doc, default=str)}")

print(f"\n── user_builds (up to 5) ───────────────────────────────")
for doc in user_col.find({}, {"_id": 0}).limit(5):
    # Truncate build_index if large
    if "build_index" in doc:
        doc["build_index"] = f"<{len(doc['build_index'])} build(s)>"
    print(f"   {json.dumps(doc, default=str)}")

# ── 5. Write / read / delete round-trip ──────────────────────────────────────
print(f"\n── Write round-trip test ───────────────────────────────")
test_id = f"__diag__{uuid.uuid4()}"
try:
    result = builds_col.insert_one({
        "build_id":    test_id,
        "canonical_name": "__diagnostic__",
        "offensive":   {},
        "defensive":   {},
        "weapon_meta": {},
        "created_at":  datetime.datetime.utcnow(),
        "updated_at":  datetime.datetime.utcnow(),
    })
    print(f"[OK]  Inserted test doc  (_id={result.inserted_id})")

    found = builds_col.find_one({"build_id": test_id}, {"_id": 0, "canonical_name": 1})
    if found:
        print(f"[OK]  Read back: {found}")
    else:
        print("[WARN] Inserted but could not read back — possible consistency lag")

    del_result = builds_col.delete_one({"build_id": test_id})
    if del_result.deleted_count == 1:
        print("[OK]  Deleted test doc")
    else:
        print("[WARN] Delete matched 0 documents")

except OperationFailure as e:
    print(f"[FAIL] Write permission error: {e}")
    print("       Check that your Atlas user has readWrite on the rox database.")
    sys.exit(1)
except Exception as e:
    print(f"[FAIL] Unexpected error during write test: {e}")
    sys.exit(1)

# ── 6. Indexes ────────────────────────────────────────────────────────────────
print(f"\n── Indexes ─────────────────────────────────────────────")
for name, idx in builds_col.index_information().items():
    print(f"   builds.{name}: {idx['key']}")
for name, idx in user_col.index_information().items():
    print(f"   user_builds.{name}: {idx['key']}")

print("\n[DONE] All checks passed.")
