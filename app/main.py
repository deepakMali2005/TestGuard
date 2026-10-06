from fastapi import FastAPI

from app.api.projects import router as projects_router


app = FastAPI(
    title="TestGuard",
    description=(
        "Evidence-Based Reliability Validation for "
        "LLM-Generated Software Tests"
    ),
    version="0.1.0",
)

app.include_router(projects_router)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "testguard",
    }