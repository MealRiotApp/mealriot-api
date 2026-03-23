from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from app.api.deps import require_active_user
from app.models.models import User
from app.schemas.food import ParseTextRequest, ParseTextResponse, ParseImageResponse, BarcodeResponse
from app.services.ai_service import parse_food_text, parse_food_image
from app.services.barcode_service import lookup_barcode

router = APIRouter(prefix="/api/v1/food", tags=["food"])

ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_IMAGE_BYTES = 10 * 1024 * 1024  # 10MB


@router.post("/parse-text", response_model=ParseTextResponse)
async def parse_text_route(
    body: ParseTextRequest,
    current_user: User = Depends(require_active_user),
):
    if not body.text.strip():
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": "INVALID_INPUT", "message": "Text cannot be empty"}},
        )
    items = await parse_food_text(body.text)
    return ParseTextResponse(items=items)


@router.post("/parse-image", response_model=ParseImageResponse)
async def parse_image_route(
    image: UploadFile = File(...),
    current_user: User = Depends(require_active_user),
):
    if image.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": "INVALID_IMAGE",
                              "message": "Image must be JPEG, PNG, or WEBP"}},
        )
    image_bytes = await image.read()
    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": "INVALID_IMAGE", "message": "Image too large (max 10MB)"}},
        )

    from app.core.config import get_settings
    from supabase import create_client
    import uuid

    settings = get_settings()
    sb = create_client(settings.supabase_url, settings.supabase_service_key)
    ext = image.content_type.split("/")[1]
    path = f"{current_user.id}/{uuid.uuid4()}.{ext}"
    sb.storage.from_("food-images").upload(path, image_bytes,
                                           {"content-type": image.content_type})
    signed = sb.storage.from_("food-images").create_signed_url(path, 60 * 60 * 24 * 365)
    image_url = signed["signedURL"]

    items = await parse_food_image(image_bytes, image.content_type)
    return ParseImageResponse(image_url=image_url, items=items)


@router.get("/barcode/{barcode}", response_model=BarcodeResponse)
async def barcode_lookup_route(
    barcode: str,
    current_user: User = Depends(require_active_user),
):
    items = await lookup_barcode(barcode)
    return BarcodeResponse(items=items)
