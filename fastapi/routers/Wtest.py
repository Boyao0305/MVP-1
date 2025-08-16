from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from database import SessionLocal
from functions.word_test import get_word_and_distractor_definitions  # ✅ 导入函数
from tools.logger import logger 
router = APIRouter(prefix="/api")

# 依赖注入：获取数据库会话
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/definition/{word_id}")
def definition_with_distractors(
    word_id: int,
    db: Session = Depends(get_db)
):
    try:
        logger.info(f"收到 definition 查询请求，word_id={word_id}")
        result = get_word_and_distractor_definitions(db, word_id)
        logger.debug(f"查询结果: {result}")
        return result
    except ValueError as e:
        logger.warning(f"未找到 word_id={word_id}，原因: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception(f"服务内部异常，word_id={word_id}")
        raise HTTPException(status_code=500, detail=f"服务内部异常: {str(e)}")
