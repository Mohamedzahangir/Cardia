"""CARDIA Backend Server.

FastAPI application providing:
- Real-time WebSocket streaming of SimulationState (~25 Hz)
- Simulation control commands (run, pause, reset, set_parameters, set_speed)
- ML inference endpoint (/api/ml/predict)
- RAG physiology reasoning endpoint (/api/rag/ask)
- Static file serving for the Stitch frontend
"""

from __future__ import annotations

import sys
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

# Ensure root workspace is in sys.path
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from backend.services.sim_service import sim_service
from backend.api.ml_routes import router as ml_router
from backend.api.rag_routes import router as rag_router
from backend.api.experiment_routes import router as experiment_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: kickoff simulation background task
    sim_service.start_loop()
    yield
    # Shutdown


app = FastAPI(
    title="CARDIA Hemodynamic Digital Twin API",
    description="Real-time clinical twin simulation, ML inference, and RAG pathophysiology explanation.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Routers
app.include_router(ml_router)
app.include_router(rag_router)
app.include_router(experiment_router)


@app.get("/health")
def health_check():
    return {
        "status": "online",
        "simulation_running": sim_service.running,
        "time_s": sim_service.state.time_s,
    }


# WebSocket endpoint for real-time bidirectional simulation control and telemetry
@app.websocket("/ws/simulation")
async def websocket_simulation_endpoint(websocket: WebSocket):
    await sim_service.register_client(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            await sim_service.handle_control_message(data)
    except WebSocketDisconnect:
        sim_service.unregister_client(websocket)
    except Exception as e:
        print(f"WebSocket client error: {e}")
        sim_service.unregister_client(websocket)


# Serve frontend static assets and index.html
FRONTEND_DIR = WORKSPACE_ROOT / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

    @app.get("/")
    async def serve_index():
        index_file = FRONTEND_DIR / "index.html"
        if index_file.exists():
            return FileResponse(str(index_file))
        return {"error": "frontend/index.html not found"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=False)
