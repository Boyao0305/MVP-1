# routers/definition_with_distractors.py (async)
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from database import SessionLocal
from functions.word_test import get_word_and_distractor_definitions
from tools.logger import logger
import inspect

router = APIRouter(prefix="/api")

# Async DB dependency
async def get_db():
    async with SessionLocal() as db:
        yield db

@router.get("/definition/{word_id}")
async def definition_with_distractors(
    word_id: int,
    db: AsyncSession = Depends(get_db),
):
    try:
        logger.info(f"收到 definition 查询请求，word_id={word_id}")

        # Support both sync and async implementations of the helper
        if inspect.iscoroutinefunction(get_word_and_distractor_definitions):
            result = await get_word_and_distractor_definitions(db, word_id)
        else:
            # Run the synchronous helper against a sync Session bound to this AsyncSession
            def _call(sync_session):
                return get_word_and_distractor_definitions(sync_session, word_id)
            result = await db.run_sync(_call)

        logger.debug(f"查询结果: {result}")
        return result
    except ValueError as e:
        logger.warning(f"未找到 word_id={word_id}，原因: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception(f"服务内部异常，word_id={word_id}")
        raise HTTPException(status_code=500, detail=f"服务内部异常: {str(e)}")
