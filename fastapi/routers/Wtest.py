from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from database import SessionLocal
from functions.word_test import get_word_and_distractor_definitions  # ✅ 导入函数

router = APIRouter(prefix="/api")

# 依赖注入：获取数据库会话
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/definition/{word}")
def definition_with_distractors(
    word: str,
    db: Session = Depends(get_db)
):
    try:
        return get_word_and_distractor_definitions(db, word)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"服务内部异常: {str(e)}")
