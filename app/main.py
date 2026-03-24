from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import HTTPException
from app.core.config import get_settings
from app.middleware.auth import prefetch_jwks
from app.api import admin as admin_module
from app.api import food as food_module
from app.api import entries as entries_module
from app.api import stats as stats_module
from app.api import recent_foods as recent_foods_module
from app.api import profile as profile_module
from app.api import pet as pet_module
from app.api import friends as friends_module
from app.api import groups as groups_module
from app.api import points as points_module
from app.api import jobs as jobs_module
from app.api import water as water_module
from app.api import weight as weight_module
from app.api import drinks as drinks_module
from app.api import goals as goals_module
from app.api import insight as insight_module

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await prefetch_jwks()
    yield


app = FastAPI(title="NutriLog API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    detail = exc.detail
    # If detail is already {"error": {...}}, return it directly
    if isinstance(detail, dict) and "error" in detail:
        return JSONResponse(status_code=exc.status_code, content=detail)
    return JSONResponse(status_code=exc.status_code, content={"detail": detail})


if settings.dev_mode:
    from app.api import dev_auth as dev_auth_module
    from app.api import dev_seed as dev_seed_module
    app.include_router(dev_auth_module.router)
    app.include_router(dev_seed_module.router)

app.include_router(admin_module.router)
app.include_router(food_module.router)
app.include_router(entries_module.router)
app.include_router(stats_module.router)
app.include_router(recent_foods_module.router)
app.include_router(profile_module.router)
app.include_router(pet_module.router)
app.include_router(friends_module.router)
app.include_router(groups_module.router)
app.include_router(points_module.router)
app.include_router(jobs_module.router)
app.include_router(water_module.router)
app.include_router(weight_module.router)
app.include_router(drinks_module.router)
app.include_router(goals_module.router)
app.include_router(insight_module.router)

@app.get("/health")
async def health():
    return {"status": "ok"}
