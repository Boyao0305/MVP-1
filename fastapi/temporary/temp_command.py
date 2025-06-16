from fastapi import APIRouter, Depends, HTTPException, Form,Request
from sqlalchemy.orm import Session
from database import SessionLocal
from crud.auth import authenticate_user, register_user
from pydantic import BaseModel
import schemas
from fastapi.responses import JSONResponse
router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/api")
async def root(request: Request):
    client_ip = request.headers.get("x-real-ip")
    forwarded_for = request.headers.get("x-forwarded-for")
    protocol = request.headers.get("x-forwarded-proto")
    host = request.headers.get("host")

    return {
        client_ip,
        forwarded_for,
        protocol,
        host
    }

@router.get("/learning_session")
def get_outline():
    return JSONResponse(content={
        "topic": "history",
        "CEFR": "B2",
        "outline": [
            "Introduction: The interconnectedness of history and modern environmental challenges.",
            "Historical Context: How colonization and wars disrupted ecosystems and biodiversity.",
            "Archaeology Insights: Artifacts and ancient treaties reveal early human impacts on habitats.",
            "Deforestation and Pollution: The legacy of industrialization and its role in climate change.",
            "Global Warming and Conflict: How resource scarcity fuels modern wars and conflicts.",
            "The Role of Renewable Energy: A revolution in sustainability to combat global warming.",
            "Conservation Efforts: Protecting biodiversity and habitats through modern treaties.",
            "Conclusion: Learning from history to build a sustainable future."
        ],
        "vocabulary": [
            {"english": "Ecosystem", "chinese": "生态系统"},
            {"english": "Biodiversity", "chinese": "生物多样性"},
            {"english": "Sustainability", "chinese": "可持续性"},
            {"english": "Pollution", "chinese": "污染"},
            {"english": "Deforestation", "chinese": "森林砍伐"},
            {"english": "Global Warming", "chinese": "全球变暖"},
            {"english": "Climate Change", "chinese": "气候变化"},
            {"english": "Renewable Energy", "chinese": "可再生能源"},
            {"english": "Conservation", "chinese": "保护"},
            {"english": "Habitat", "chinese": "栖息地"},
            {"english": "Colonization", "chinese": "殖民"},
            {"english": "Revolution", "chinese": "革命"},
            {"english": "War", "chinese": "战争"},
            {"english": "Conflict", "chinese": "冲突"},
            {"english": "Treaty", "chinese": "条约"},
            {"english": "Archaeology", "chinese": "考古学"},
            {"english": "Artifact", "chinese": "文物"}
        ]
    })
