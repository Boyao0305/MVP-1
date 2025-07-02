from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi import HTTPException  # optional, if used inside a FastAPI route
from typing import Optional
import models  # ← your ORM models


def update_average_caiji_for_user(user_id: int, db: Session) -> Optional[float]:
    """
    Re-computes average daily_caiji over the 5 newest learning logs
    (with non-empty `artical`) for the given user and stores the result
    in `learning_settings.average_caiji`.

    Returns
    -------
    float | None
        The newly-calculated average, or None if no qualifying logs exist.

    Raises
    ------
    HTTPException(404)
        If the user has no Learning_setting row (adjust as you like).
    """
    # ── 1️⃣  five newest logs for this user
    recent_subq = (
        db.query(models.Learning_log)
          .filter(models.Learning_log.user_id == user_id)
          .order_by(models.Learning_log.id.desc())
          .limit(5)
          .subquery()
    )

    # ── 2️⃣  average daily_caiji where artical not null / not empty
    avg_caiji: Optional[float] = (
        db.query(func.avg(recent_subq.c.daily_caiji))
          .filter(recent_subq.c.artical.isnot(None))
          .filter(recent_subq.c.artical != "")
          .scalar()
    )

    # Nothing to update if no qualifying rows
    if avg_caiji is None:
        return None

    # ── 3️⃣  write the value into learning_settings
    setting = (
        db.query(models.Learning_setting)
          .filter(models.Learning_setting.user_id == user_id)
          .first()
    )
    if setting is None:
        raise HTTPException(status_code=404,
                            detail="Learning_setting not found for this user")

    setting.average_caiji = avg_caiji
    db.commit()
    db.refresh(setting)

    return avg_caiji
