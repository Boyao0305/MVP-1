from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
import schemas2 as schemas
from database import SessionLocal

from tools.service_functions import promote_unlearned_per_tag

router = APIRouter(prefix="/api")
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post(
    "/initial_learning/{user_id}",
    response_model=list[schemas.TagWordsOut],
    summary="Promote up to 60 unlearned words *per tag* from word-book 1"
)
def initial_learning_batch(user_id: int, db: Session = Depends(get_db)):
    promoted = promote_unlearned_per_tag(user_id, db)   # tag ➜ [Word_status,…]

    # Build the JSON-friendly objects that include learning_factor
    return [
        schemas.TagWordsOut(
            tag=tag,
            words=[
                schemas.WordBatchOut(
                    id=ws.l_words.id,
                    word=ws.l_words.word,
                    CEFR=ws.l_words.CEFR,
                    learning_factor=ws.learning_factor,
                )
                for ws in ws_rows
            ],
        )
        for tag, ws_rows in promoted.items()
    ]