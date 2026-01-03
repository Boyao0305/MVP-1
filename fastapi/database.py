import argparse
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import create_engine

def create_sync_database():
    DATABASE_URL = "mysql+pymysql://user:password@mysql:3306/mydatabase"
    
    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(bind=engine)
    
    Base = declarative_base()

    return SessionLocal, engine, Base

def create_async_database():
    DATABASE_URL = "mysql+aiomysql://user:password@mysql:3306/mydatabase"

    engine = create_async_engine(
        DATABASE_URL, echo=False
    )
    SessionLocal = sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False
    )
    Base = declarative_base()

    return SessionLocal, engine, Base

parser = argparse.ArgumentParser(description="A script with sync/async modes.")

# Define the 'mode' argument
parser.add_argument(
    '--mode', 
    choices=['sync', 'async'], 
    default='async',
    help="Set the execution mode (default: sync)"
)

args = parser.parse_args()

if args.mode == 'sync':
    SessionLocal, engine, Base = create_sync_database()
if args.mode == 'async':
    SessionLocal, engine, Base = create_async_database()
