from fastapi import APIRouter, Depends, HTTPException, Form
from sqlalchemy.orm import Session
from database import SessionLocal
from crud.auth import authenticate_user, register_user
from pydantic import BaseModel
import schemas2
import models


router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/receive_data")
def receive_data(data: schemas2.Receive_data, db: Session = Depends(get_db)):
    return data

