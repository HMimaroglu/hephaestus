import asyncio
import logging
import time
from contextlib import asynccontextmanager
from typing import List, Optional
import psutil
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.settings import settings
from backend.discovery import DiscoveryService
from backend.ws_server import WebSocketServer
from backend.role_manager import RoleManager
from backend.router import TaskRouter
from backend.state_sync import StateSyncService
from backend.llm import llm_adapter
from backend.schemas import NodeHealth, PeerInfo, TaskRecord

logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

role_manager = RoleManager()
ws_server = WebSocketServer(router=None, role_manager=role_manager)
discovery_service = DiscoveryService(role_manager=role_manager, ws_server=ws_server)
task_router = TaskRouter(
    role_manager=role_manager,
    discovery_service=discovery_service,
    ws_server=ws_server
)
state_sync_service = StateSyncService(
    role_manager=role_manager,
    ws_server=ws_server
)

ws_server.router = task_router

start_time = time.time()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting Hephaestus node: {settings.node_id}")

    await role_manager.initialize()
    await discovery_service.start()
    await ws_server.start()
    await state_sync_service.start()

    load_monitor_task = asyncio.create_task(periodic_load_check())

    logger.info(f"Node started on {settings.host}:{settings.port}")
    logger.info(f"WebSocket server on {settings.host}:{settings.ws_port}")
    logger.info(f"Discovery on port {settings.discovery_port}")
    logger.info(f"Active roles: {role_manager.get_active_roles()}")

    yield

    logger.info("Shutting down node...")
    load_monitor_task.cancel()
    await state_sync_service.stop()
    await ws_server.stop()
    await discovery_service.stop()
    logger.info("Node shut down complete")


app = FastAPI(
    title="Hephaestus Node",
    description="Adaptive Offline AI Mesh Node",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def periodic_load_check():
    while True:
        try:
            await asyncio.sleep(30)
            await role_manager.check_load_and_negotiate(ws_server)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Error in load check: {e}")


class TaskSubmitRequest(BaseModel):
    role: str
    prompt: str
    context: Optional[dict] = None
    priority: int = 1


class TaskSubmitResponse(BaseModel):
    task_id: str
    status: str


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    try:
        with open("web/index.html", "r") as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        return HTMLResponse(content="<h1>Hephaestus Node</h1><p>Dashboard not found</p>")


@app.get("/health", response_model=NodeHealth)
async def health():
    uptime = time.time() - start_time
    cpu = psutil.cpu_percent(interval=0.1)
    mem = psutil.virtual_memory().percent

    return NodeHealth(
        node_id=settings.node_id,
        node_name=settings.node_name,
        uptime=uptime,
        cpu_percent=cpu,
        memory_percent=mem,
        active_roles=role_manager.get_active_roles(),
        active_tasks=sum(role_manager.active_tasks.values()),
        peer_count=len(discovery_service.get_peers()) + len(ws_server.peer_registry),
        load=role_manager.get_load(),
        qos=role_manager.get_qos()
    )


@app.get("/peers", response_model=List[PeerInfo])
async def list_peers():
    multicast_peers = discovery_service.get_peers()
    ws_peers = ws_server.peer_registry
    all_peers = {**multicast_peers, **ws_peers}
    return list(all_peers.values())


@app.get("/roles")
async def list_roles():
    return {
        "active_roles": role_manager.get_active_roles(),
        "tasks_per_role": role_manager.active_tasks
    }


@app.post("/roles/{role_name}")
async def add_role(role_name: str):
    success = await role_manager.add_role(role_name)
    if success:
        return {"status": "success", "role": role_name}
    else:
        raise HTTPException(status_code=400, detail=f"Failed to add role {role_name}")


@app.delete("/roles/{role_name}")
async def remove_role(role_name: str):
    success = await role_manager.remove_role(role_name)
    if success:
        return {"status": "success", "role": role_name}
    else:
        raise HTTPException(status_code=404, detail=f"Role {role_name} not found")


@app.post("/tasks", response_model=TaskSubmitResponse)
async def submit_task(request: TaskSubmitRequest):
    task_id = await task_router.submit_task(
        role=request.role,
        prompt=request.prompt,
        context=request.context,
        priority=request.priority
    )
    return TaskSubmitResponse(task_id=task_id, status="submitted")


@app.get("/tasks", response_model=List[TaskRecord])
async def list_tasks():
    return task_router.get_all_tasks()


@app.get("/tasks/{task_id}", response_model=TaskRecord)
async def get_task_status(task_id: str):
    task = task_router.get_task_status(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@app.get("/tasks/{task_id}/wait")
async def wait_for_task(task_id: str, timeout: int = 120):
    try:
        result = await task_router.wait_for_task(task_id, timeout=timeout)
        return result
    except asyncio.TimeoutError:
        raise HTTPException(status_code=408, detail="Task timeout")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/llm/health")
async def llm_health():
    healthy = await llm_adapter.health_check()
    return {
        "status": "healthy" if healthy else "unhealthy",
        "backend": settings.llm_backend,
        "model": settings.llm_model,
        "host": settings.llm_host
    }


@app.get("/events")
async def events():
    async def event_generator():
        while True:
            health_data = await health()
            peers = await list_peers()
            tasks = await list_tasks()

            event_data = {
                "health": health_data.model_dump(),
                "peers": [p.model_dump(mode='json') for p in peers],
                "tasks": [t.model_dump(mode='json') for t in tasks[-10:]]
            }

            yield f"data: {event_data}\n\n"
            await asyncio.sleep(2)

    from fastapi.responses import StreamingResponse
    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/api/demo/test")
async def demo_test():
    return {
        "message": "Hephaestus node is running",
        "node_id": settings.node_id,
        "roles": role_manager.get_active_roles(),
        "peers": len(discovery_service.get_peers())
    }


try:
    app.mount("/web", StaticFiles(directory="web"), name="web")
except Exception as e:
    logger.warning(f"Could not mount /web directory: {e}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.app:app",
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
        reload=False
    )
