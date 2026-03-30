from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Request
from app.api.deps import require_active_user
from app.middleware.rate_limit import limiter
from app.models.models import User
from app.schemas.feedback import FeedbackResponse
from app.services import feedback_service

router = APIRouter(prefix="/api/v1/feedback", tags=["feedback"])

MAX_SCREENSHOT_BYTES = 5 * 1024 * 1024  # 5MB


@router.post("", response_model=FeedbackResponse)
@limiter.limit("3/hour")
async def submit_feedback(
    request: Request,
    message: str = Form(..., max_length=1000),
    screen_width: int | None = Form(None),
    screen_height: int | None = Form(None),
    page_url: str | None = Form(None),
    screenshot: UploadFile | None = File(None),
    current_user: User = Depends(require_active_user),
):
    screenshot_data = None
    screenshot_filename = None

    if screenshot:
        screenshot_data = await screenshot.read()
        if len(screenshot_data) > MAX_SCREENSHOT_BYTES:
            raise HTTPException(
                status_code=413,
                detail={"error": {"code": "FILE_TOO_LARGE", "message": "Screenshot must be under 5MB"}},
            )
        screenshot_filename = screenshot.filename or "screenshot.png"

    user_agent = request.headers.get("user-agent", "Unknown")

    try:
        await feedback_service.send_feedback_email(
            user_name=current_user.name,
            user_email=current_user.email,
            message=message,
            user_agent=user_agent,
            screen_width=screen_width,
            screen_height=screen_height,
            page_url=page_url,
            screenshot_data=screenshot_data,
            screenshot_filename=screenshot_filename,
        )
    except RuntimeError:
        raise HTTPException(
            status_code=503,
            detail={"error": {"code": "SMTP_NOT_CONFIGURED", "message": "Feedback service is not available"}},
        )

    return FeedbackResponse(status="sent")
