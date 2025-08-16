from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
#
# DATABASE_URL = "mysql+pymysql://user:password@mysql:3306/mydatabase"
#
# engine = create_engine(DATABASE_URL)
# SessionLocal = sessionmaker(bind=engine)
#
# Base = declarative_base()

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base

engine = create_async_engine(
    "mysql+aiomysql://user:password@mysql:3306/mydatabase", echo=False
)
SessionLocal = sessionmaker(
    bind=engine, class_=AsyncSession, expire_on_commit=False
)
Base = declarative_base()