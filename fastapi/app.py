from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import auth,data_receive
from temporary import temp_command
from database import Base, engine
Base.metadata.create_all(bind=engine)
import test
from tools import service_router
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # or specify your frontend's address
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(auth.router)
app.include_router(temp_command.router)

app.include_router(test.router)
app.include_router(data_receive.router)
app.include_router(service_router.router)


# @app.get("/")
# async def root(request: Request):
#     client_ip = request.headers.get("x-real-ip")
#     forwarded_for = request.headers.get("x-forwarded-for")
#     protocol = request.headers.get("x-forwarded-proto")
#     host = request.headers.get("host")
#
#     return {
#         client_ip,
#         forwarded_for,
#         protocol,
#         host
#     }
#
# @app.get("/outline")
# def get_outline():
#     return {today_outline}
#
# @app.get("/topic")
# def get_topic():
#     return {today_topic}
#
# @app.get("/word")
# def get_word():
#     return {today_word}
#
# @app.get("/cefr")
# def get_cefr():
#     return {CEFR}



