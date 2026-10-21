
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.agents.image_agent import image_agent

router = APIRouter(prefix="/api/image", tags=["Image Agent"])


class ImageRequest(BaseModel):
    product: str = Field(min_length=1, max_length=200)
    audience: str = Field(min_length=1, max_length=300)
    objective: str = "Sales"
    tone: str = "Professional"
    instructions: str = ""
    placement: str = "Instagram Feed"


@router.post("/generate")
def generate_ad_image(request: ImageRequest):
    try:
        result = image_agent.generate_image(
            product=request.product,
            audience=request.audience,
            objective=request.objective,
            tone=request.tone,
            instructions=request.instructions,
            placement=request.placement,
        )

        return result

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    except Exception:
        # Avoid exposing API keys or internal error details
        raise HTTPException(
            status_code=502,
            detail="Image generation failed. Check server logs and API configuration."
        )