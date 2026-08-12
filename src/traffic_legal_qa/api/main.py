from fastapi import FastAPI

from traffic_legal_qa import __version__

app = FastAPI(
    title="Vietnamese Traffic Law Legal QA",
    version=__version__,
    description="Version-aware legal QA over Vietnamese traffic-law documents.",
)


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}
