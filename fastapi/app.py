from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
from fastapi.routing import APIRoute
from starlette.routing import WebSocketRoute
from routers import initiation1, routine, advanced_options,tts, Wtest, phone_number
from routers2 import initiation2, routine2, advanced_options2,tts2, Wtest2, phone_number2
logger = logging.getLogger("uvicorn")

from website import api1,generation, dictionary
from tools.English_specialist_api import composition_word
from database import Base, engine
# Base.metadata.create_all(bind=engine)
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

@app.on_event("startup")
async def on_startup():

    async with engine.begin() as conn:
        # optional: await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    for r in app.router.routes:
        if isinstance(r, APIRoute):
            logger.info(f"HTTP {list(r.methods)} {r.path}")
        elif isinstance(r, WebSocketRoute):
            logger.info(f"WS {r.path}")
@app.get("/_debug/routes")
def debug_routes():
    out = []
    for r in app.router.routes:
        kind = "websocket" if isinstance(r, WebSocketRoute) else "http"
        methods = list(getattr(r, "methods", []))
        out.append({"path": r.path, "type": kind, "methods": methods})
    return out
app.include_router(advanced_options.router)
app.include_router(initiation1.router)
app.include_router(phone_number.router)
app.include_router(routine.router)
app.include_router(tts.router)
app.include_router(Wtest.router)

app.include_router(advanced_options2.router)
app.include_router(initiation2.router)
app.include_router(phone_number2.router)
app.include_router(routine2.router)
app.include_router(tts2.router)
app.include_router(Wtest2.router)
# for route in app.routes:
#     print(route.path)
# app.include_router(test.router)
#
# app.include_router(service_router.router)
# app.include_router(api1.router)
# app.include_router(generation.router)
# # app.include_router(dictionary.router)
# app.include_router(composition_word.router)



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



