# functions/cefr2_update_average_caiji.py — async version
from __future__ import annotations

from typing import Optional

from fastapi import HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

import models  # ORM models


async def update_average_caiji_for_user(user_id: int, db: AsyncSession) -> Optional[float]:
    """
    Re-compute average daily_caiji over the 5 newest learning logs (with non-empty
    `artical`) for the given user and store it in `learning_settings.average_caiji`.

    Returns
    -------
    float | None
        Newly calculated average, or None if no qualifying logs exist.

    Raises
    ------
    HTTPException(404)
        If the user has no Learning_setting row.
    """
    # 1) five newest logs for this user (only needed columns)
    recent_subq = (
        select(
            models.Learning_log.id,
            models.Learning_log.daily_caiji,
            models.Learning_log.artical,
        )
        .where(models.Learning_log.user_id == user_id)
        .order_by(models.Learning_log.id.desc())
        .limit(5)
        .subquery()
    )

    # 2) average daily_caiji where artical not null / not empty
    avg_caiji = await db.scalar(
        select(func.avg(recent_subq.c.daily_caiji)).where(
            recent_subq.c.artical.isnot(None),
            recent_subq.c.artical != "",
        )
    )

    # Nothing to update if no qualifying rows
    if avg_caiji is None:
        return None

    # 3) write the value into learning_settings
    setting = (
        await db.execute(
            select(models.Learning_setting).where(models.Learning_setting.user_id == user_id)
        )
    ).scalars().first()

    if setting is None:
        raise HTTPException(
            status_code=404, detail="Learning_setting not found for this user"
        )

    setting.average_caiji = float(avg_caiji)
    await db.commit()
    await db.refresh(setting)

    return float(avg_caiji)
