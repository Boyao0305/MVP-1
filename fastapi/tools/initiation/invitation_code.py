#!/usr/bin/env python3
"""
Generate and insert 50 random invitation codes (e.g. "skcueb")
into the Invitation_code table.

Assumptions
-----------
• You already have a SQLAlchemy `models.py` declaring:

    class Invitation_code(Base):
        __tablename__ = "invitation_codes"
        id          = Column(Integer, primary_key=True)
        code        = Column(String(6), unique=True, index=True, nullable=False)
        code_status = Column(Integer, default=0, nullable=False)

• Your database URL is available as an environment variable, or you can
  paste it directly into DATABASE_URL below.

Usage
-----
$ python insert_invitation_codes.py
"""

import os
import random
import string
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import sys
import os
import pandas as pd
from fastapi import HTTPException
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..','..')))
from database import SessionLocal, engine, Base
# Create tables

import os, random, string
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError
from models import Invitation_code  # <- uses *exactly* the same Base as models.py

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "mysql+pymysql://user:password@localhost:3306/mydatabase",
)
engine = create_engine(DATABASE_URL, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, future=True)


def random_code() -> str:
    return "".join(random.choices(string.ascii_lowercase, k=6))


def insert_invitation_codes(n: int = 50) -> None:
    session = SessionLocal()
    inserted = 0

    while inserted < n:
        code = random_code()
        session.add(Invitation_code(code=code, code_status=0))
        try:
            session.commit()
            inserted += 1
        except IntegrityError:
            # Duplicate code → rollback and try again
            session.rollback()

    session.close()
    print(f"✅  Inserted {inserted} unique invitation codes.")


if __name__ == "__main__":
    insert_invitation_codes()