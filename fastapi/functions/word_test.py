from sqlalchemy.orm import Session
from sqlalchemy.sql import func
import models

def get_word_and_distractor_definitions(db: Session, word: str):
    # 查找目标单词的定义
    word_entry = db.query(models.Word).filter(models.Word.word == word).first()
    if not word_entry:
        raise ValueError("Target word not found in database")

    # 获取目标单词的定义
    target_definition = word_entry.definition

    # 随机选取3个其它单词的定义（不包含自己）
    distractors = (
        db.query(models.Word.definition)
        .filter(models.Word.word != word)
        .order_by(func.rand())  # PostgreSQL / SQLite；若是 MySQL 改为 func.rand()
        .limit(3)
        .all()
    )
    # 将 (definition,) 元组列表转成字符串列表
    distractor_definitions = [d[0] for d in distractors]

    return {
        "word": word,
        "definition": target_definition,
        "distractors": distractor_definitions
    }
