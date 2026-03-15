"""
Migration script to upload legacy moves and videos to Acro Hub.

Usage:
    python migrate.py

The script will prompt for your username (email) and password, then
sequentially create each move from legacy_moves.json and upload any
associated demo video from the migration/videos/ directory.

Expected directory layout:
    migration/
        legacy_moves.json
        migrate.py          ← this file
        videos/
            <filename>.mp4
            ...
"""

import getpass
import json
import os
import sys
import uuid

import requests

API_BASE = "https://api.acrohub.org"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LEGACY_MOVES_PATH = os.path.join(SCRIPT_DIR, "legacy_moves.json")
VIDEOS_DIR = os.path.join(SCRIPT_DIR, "videos")


def map_difficulty(numeric: int) -> str:
    """Convert a numeric difficulty (1–10) to the API difficulty string."""
    if numeric <= 3:
        return "easy"
    if numeric <= 6:
        return "medium"
    if numeric <= 8:
        return "hard"
    return "expert"


def login(email: str, password: str) -> str:
    """Authenticate and return the idToken JWT."""
    resp = requests.post(
        f"{API_BASE}/auth/login",
        json={"email": email, "password": password},
        timeout=30,
    )
    if resp.status_code != 200:
        print(f"Login failed ({resp.status_code}): {resp.text}")
        sys.exit(1)
    token = resp.json().get("idToken")
    if not token:
        print("Login response did not contain an idToken.")
        sys.exit(1)
    return token


def create_move(token: str, move_data: dict) -> dict:
    """POST a new move and return the created move object."""
    resp = requests.post(
        f"{API_BASE}/moves",
        json=move_data,
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def get_upload_url(token: str, move_id: str) -> dict:
    """Request a pre-signed S3 upload URL for the given move."""
    resp = requests.post(
        f"{API_BASE}/videos/{move_id}/upload-url",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def upload_video(upload_url: str, video_path: str) -> None:
    """PUT a local video file to the pre-signed S3 URL."""
    with open(video_path, "rb") as fh:
        resp = requests.put(
            upload_url,
            data=fh,
            headers={"Content-Type": "video/mp4"},
            timeout=300,
        )
    resp.raise_for_status()


def main() -> None:
    print("Acro Hub — legacy migration script")
    print("====================================")
    email = input("Email: ").strip()
    password = getpass.getpass("Password: ")

    print("\nLogging in…")
    token = login(email, password)
    print("Login successful.\n")

    with open(LEGACY_MOVES_PATH, encoding="utf-8") as fh:
        legacy_moves = json.load(fh)

    total = len(legacy_moves)
    moves_created = 0
    moves_failed = 0
    videos_uploaded = 0
    videos_failed = 0

    for idx, (_key, entry) in enumerate(legacy_moves.items(), start=1):
        name = entry.get("name", "").strip()
        numeric_difficulty = entry.get("difficulty", 1)
        demo_filename = entry.get("videos", {}).get("demo")

        difficulty = map_difficulty(numeric_difficulty)
        video_key = str(uuid.uuid4()) if demo_filename else ""

        move_data = {
            "name": name,
            "description": "",
            "difficulty": difficulty,
            "tags": [],
            "category": None,
            "videoKey": video_key,
        }

        print(f"[{idx}/{total}] Creating move: {name!r} (difficulty={difficulty})", end="")

        try:
            created = create_move(token, move_data)
        except requests.HTTPError as exc:
            print(f" — FAILED to create: {exc}")
            moves_failed += 1
            continue

        move_id = created.get("moveId")
        print(f" → moveId={move_id}", end="")
        moves_created += 1

        if demo_filename:
            video_path = os.path.join(VIDEOS_DIR, demo_filename)
            if not os.path.isfile(video_path):
                print(f" — WARNING: video file not found: {video_path}")
                videos_failed += 1
                continue

            try:
                upload_info = get_upload_url(token, move_id)
                upload_url = upload_info.get("uploadUrl")
                if not upload_url:
                    print(" — WARNING: no uploadUrl in response")
                    videos_failed += 1
                    continue
                upload_video(upload_url, video_path)
                print(" — video uploaded ✓")
                videos_uploaded += 1
            except (requests.HTTPError, OSError) as exc:
                print(f" — WARNING: failed to upload video: {exc}")
                videos_failed += 1
        else:
            print(" — no video")

    print(f"\nDone.")
    print(f"  Moves  : {moves_created}/{total} created, {moves_failed} failed.")
    print(f"  Videos : {videos_uploaded} uploaded, {videos_failed} failed.")


if __name__ == "__main__":
    main()
