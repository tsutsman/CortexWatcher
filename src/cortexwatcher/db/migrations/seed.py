"""Простий скрипт наповнення прикладами."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from cortexwatcher.db.models import LogRaw
from cortexwatcher.db.session import async_session_maker


async def seed() -> None:
    async with async_session_maker() as session:
        sample = LogRaw(
            source="seed",
            received_at=datetime.now(timezone.utc),
            payload_raw="seed",
            format="text",
            hash="seed",
        )
        session.add(sample)
        await session.commit()


def main() -> None:
    asyncio.run(seed())


if __name__ == "__main__":
    main()
