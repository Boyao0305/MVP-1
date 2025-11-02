import asyncio
import os, sys
from sqlalchemy import select
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession
  # <-- ensure you have this

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
import models
from database import SessionLocal

async def legality():
    async with SessionLocal() as db:
        ws_result = await db.execute(
            select(models.Word)
            .options(
                joinedload(models.Word.l_tags)
            )
            .where(models.Word.l_tags.any(models.Tag.name == "Politics"))
        )
        ws_rows = ws_result.unique().scalars().all()
        for row in ws_rows:
            print(row.word)
            row.legality = "false"
            await db.commit()
            # await db.refresh(setting)

if __name__ == "__main__":
    asyncio.run(legality())
