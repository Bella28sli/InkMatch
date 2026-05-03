from __future__ import annotations

import argparse

import requests
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.enums import MediaType
from app.models.sketches import SketchMedia
from app.services.image_hash_service import compute_phash
from app.services.media_service import resolve_media_url


def backfill_phash(limit: int, commit: bool) -> tuple[int, int]:
    updated = 0
    skipped = 0

    with SessionLocal() as db:
        rows = db.execute(
            select(SketchMedia)
            .where(SketchMedia.media_type == MediaType.image, SketchMedia.phash.is_(None))
            .order_by(SketchMedia.created_at.asc())
            .limit(limit)
        ).scalars().all()

        for row in rows:
            url = resolve_media_url(row.url)
            if not url:
                skipped += 1
                continue

            try:
                response = requests.get(url, timeout=20)
                response.raise_for_status()
            except requests.RequestException:
                skipped += 1
                continue

            phash = compute_phash(response.content)
            if not phash:
                skipped += 1
                continue

            row.phash = phash
            updated += 1

        if commit:
            db.commit()
        else:
            db.rollback()

    return updated, skipped


def main() -> None:
    parser = argparse.ArgumentParser(description='Backfill phash for existing sketch media.')
    parser.add_argument('--limit', type=int, default=500)
    parser.add_argument('--commit', action='store_true')
    args = parser.parse_args()

    updated, skipped = backfill_phash(limit=max(1, args.limit), commit=args.commit)
    mode = 'committed' if args.commit else 'dry-run'
    print(f'{mode}: updated={updated}, skipped={skipped}')


if __name__ == '__main__':
    main()
