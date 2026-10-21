import os
import uuid
from pathlib import Path

from dotenv import load_dotenv
from huggingface_hub import InferenceClient

from app.agents.state import PipelineState


# ============================================================
# ENVIRONMENT
# ============================================================

load_dotenv()

HF_TOKEN = os.getenv("HF_TOKEN")

if not HF_TOKEN:
    raise RuntimeError("HF_TOKEN is missing from .env")


# ============================================================
# HUGGING FACE CONFIGURATION
# ============================================================

MODEL = "stabilityai/stable-diffusion-3-medium-diffusers"

client = InferenceClient(
    provider="hf-inference",
    api_key=HF_TOKEN,
)


# ============================================================
# OUTPUT DIRECTORY
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[2]

OUTPUT_DIR = BASE_DIR / "static" / "generated"

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


# ============================================================
# ASPECT RATIOS
# ============================================================

ASPECT_RATIOS = {
    "instagram_feed": (1024, 1024),
    "instagram_stories": (768, 1344),
    "instagram_reels": (768, 1344),
    "instagram_explore": (1024, 1024),
    "facebook_feed": (1024, 1024),
    "facebook_stories": (768, 1344),
    "facebook_reels": (768, 1344),
}


def get_image_size(placement: str) -> tuple[int, int]:

    placement = placement.lower().strip()

    return ASPECT_RATIOS.get(
        placement,
        (1024, 1024),
    )


# ============================================================
# IMAGE AGENT
# ============================================================

class ImageAgent:

    # --------------------------------------------------------
    # Create Prompt
    # --------------------------------------------------------

    def create_prompt(
        self,
        product: str,
        audience: str,
        objective: str,
        tone: str,
        instructions: str = "",
        placement: str = "instagram_feed",
    ) -> str:

        return f"""
Create a professional, high-quality social media advertising image.

Product or service:
{product}

Target audience:
{audience}

Campaign objective:
{objective}

Creative tone:
{tone}

Placement:
{placement}

Additional product information:
{instructions}

Visual requirements:

- Create an eye-catching commercial advertisement.
- Make the product the main visual focus.
- Use professional product photography.
- Use realistic lighting.
- Use realistic textures and details.
- Use an attractive composition.
- Match the colors and atmosphere to the product.
- Make the subject clearly visible.
- Create a premium advertising appearance.
- Leave clean negative space for a headline and CTA.
- Suitable for Instagram and Facebook advertising.
- Do not create fake logos.
- Do not create watermarks.
- Do not generate unnecessary text.
- Do not invent product features.
- Do not invent discounts or claims.
- Create an original visual.
- Generate the image only.
"""


    # --------------------------------------------------------
    # Generate Image
    # --------------------------------------------------------

    def generate_image(
        self,
        product: str,
        audience: str,
        objective: str = "sales",
        tone: str = "professional",
        instructions: str = "",
        placement: str = "instagram_feed",
    ) -> dict:

        if not product.strip():
            raise ValueError(
                "Product is required"
            )

        if not audience.strip():
            raise ValueError(
                "Audience is required"
            )

        # Create prompt
        prompt = self.create_prompt(
            product=product,
            audience=audience,
            objective=objective,
            tone=tone,
            instructions=instructions,
            placement=placement,
        )

        # Determine image dimensions
        width, height = get_image_size(
            placement
        )

        print("\nGenerating image...")
        print(
            f"Model: {MODEL}"
        )
        print(
            f"Size: {width}x{height}"
        )

        # ----------------------------------------------------
        # Hugging Face Text-to-Image
        # ----------------------------------------------------

        image = client.text_to_image(
            prompt=prompt,
            model=MODEL,
            width=width,
            height=height,
            num_inference_steps=28,
            guidance_scale=7.0,
        )

        if image is None:
            raise RuntimeError(
                "Hugging Face did not return an image"
            )

        # ----------------------------------------------------
        # Save image locally
        # ----------------------------------------------------

        filename = (
            f"{uuid.uuid4().hex}.png"
        )

        filepath = (
            OUTPUT_DIR / filename
        )

        image.save(filepath)

        print(
            f"Image saved: {filepath}"
        )

        # ----------------------------------------------------
        # Return result
        # ----------------------------------------------------

        return {
            "success": True,
            "source": "huggingface",
            "model": MODEL,
            "filename": filename,
            "image_url": (
                f"/static/generated/{filename}"
            ),
            "path": str(filepath),
            "generated": True,
            "placement": placement,
            "width": width,
            "height": height,
            "prompt": prompt,
        }


# ============================================================
# CREATE IMAGE AGENT
# ============================================================

image_agent = ImageAgent()


# ============================================================
# LANGGRAPH IMAGE AGENT
# ============================================================

def run_image_agent(
    state: PipelineState
) -> PipelineState:

    # --------------------------------------------------------
    # Stop if previous agent failed
    # --------------------------------------------------------

    if state.get("halted"):
        return state

    brief = state.get(
        "brief",
        {}
    )

    # --------------------------------------------------------
    # Check creative choice
    # --------------------------------------------------------

    creative_choice = brief.get(
        "creative_choice",
        "generate",
    )

    uploaded_assets = brief.get(
        "uploaded_asset_urls"
    ) or []

    # --------------------------------------------------------
    # If upload was selected
    # --------------------------------------------------------

    if (
        creative_choice == "upload"
        and uploaded_assets
    ):

        state["image"] = {
            "success": True,
            "source": "upload",
            "model": None,
            "filename": None,
            "image_url": uploaded_assets[0],
            "path": None,
            "generated": False,
            "asset_urls": uploaded_assets,
        }

        state["current_node"] = "image"

        return state

    # --------------------------------------------------------
    # Generate image
    # --------------------------------------------------------

    try:

        product = brief.get(
            "product",
            "",
        )

        audience = brief.get(
            "audience_description",
            "General audience",
        )

        objective = brief.get(
            "objective",
            "sales",
        )

        tone = state.get(
            "brand_voice",
            "professional",
        )

        instructions = brief.get(
            "selling_points",
            "",
        )

        placement = brief.get(
            "placement",
            "instagram_feed",
        )

        # ----------------------------------------------------
        # If placement is auto, use Instagram feed
        # ----------------------------------------------------

        if placement == "auto":

            placement = "instagram_feed"

        # ----------------------------------------------------
        # Generate
        # ----------------------------------------------------

        result = image_agent.generate_image(

            product=product,

            audience=audience,

            objective=objective,

            tone=tone,

            instructions=instructions,

            placement=placement,
        )

        # ----------------------------------------------------
        # Store image result in shared state
        # ----------------------------------------------------

        state["image"] = result

        state["current_node"] = "image"

        return state

    except Exception as e:

        print(
            f"Image agent failed: {e}"
        )

        state.setdefault(
            "errors",
            []
        ).append(
            f"image_agent: {e}"
        )

        state["halted"] = True

        state["halt_reason"] = (
            "Image agent failed to generate image"
        )

        state["current_node"] = "image"

        return state