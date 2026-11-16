"""FastAPI app. Routes stay thin: every number comes from `lookups.py`."""

from fastapi import FastAPI


def create_app() -> FastAPI:
    app = FastAPI(title="ask-analytics")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
