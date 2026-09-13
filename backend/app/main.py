from fastapi import FastAPI

app = FastAPI(
    title="FarmTwin API",
    version="0.1.0",
)


@app.get("/")
async def root() -> dict[str, str]:
    return {"message": "FarmTwin API"}


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
