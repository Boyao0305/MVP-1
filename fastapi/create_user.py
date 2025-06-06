from pygments.lexers import data

from database import SessionLocal, engine
from models import User
import bcrypt

# Create tables
from database import Base
Base.metadata.create_all(bind=engine)

# Create a test user
db = SessionLocal()

username = "testuser"
password = "mypassword"
hashed_pw = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
phone_number = 1

user = User(username=username, hashed_password=hashed_pw.decode('utf-8'),phone_number= phone_number)
db.add(user)
db.commit()



db.close()