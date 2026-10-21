from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.agents.image_agent import image_agent
from app.api.deps import get_current_user
from app.models.user import User

router = APIRouter(prefix="/api/image", tags=["image"])


class ImageGenerateRequest(BaseModel):
    product: str
    audience: str
    objective: str = "sales"
    tone: str = "professional"
    instructions: str = ""
    placement: str = "instagram_feed"


class ImageGenerateResponse(BaseModel):
    success: bool
    source: str
    model: str | None = None
    filename: str | None = None
    image_url: str
    placement: str
    width: int
    height: int


@router.post("/generate", response_model=ImageGenerateResponse)
def generate_image(
    payload: ImageGenerateRequest,
    user: User = Depends(get_current_user),
):
    """Generates an ad creative image via Hugging Face Stable Diffusion.
    Requires login (same as every other endpoint except auth itself)."""
    try:
        result = image_agent.generate_image(
            product=payload.product,
            audience=payload.audience,
            objective=payload.objective,
            tone=payload.tone,
            instructions=payload.instructions,
            placement=payload.placement,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Image generation failed: {e}") from e

    return result