import asyncio
import logging
import uuid
from typing import Dict, Optional, List
from datetime import datetime
from backend.settings import settings
from backend.schemas import (
    TaskMessage, ResultMessage, TaskRecord, TaskStatus,
    Message, MessageType, PeerInfo
)

logger = logging.getLogger(__name__)


class TaskRouter:

    def __init__(self, role_manager=None, discovery_service=None, ws_server=None):
        self.role_manager = role_manager
        self.discovery_service = discovery_service
        self.ws_server = ws_server
        self.tasks: Dict[str, TaskRecord] = {}
        self.pending_results: Dict[str, asyncio.Future] = {}

    async def submit_task(self, role: str, prompt: str, context: Dict = None, priority: int = 1) -> str:
        task_id = str(uuid.uuid4())
        task = TaskMessage(
            task_id=task_id,
            role=role,
            prompt=prompt,
            context=context or {},
            priority=priority
        )

        task_record = TaskRecord(
            task_id=task_id,
            role=role,
            prompt=prompt,
            status=TaskStatus.PENDING
        )
        self.tasks[task_id] = task_record

        asyncio.create_task(self._route_task(task))

        logger.info(f"Submitted task {task_id} for role {role}")
        return task_id

    async def _route_task(self, task: TaskMessage):
        if self.role_manager.has_role(task.role):
            await self._execute_local_task(task)
        else:
            await self._delegate_task(task)

    async def _execute_local_task(self, task: TaskMessage):
        task_record = self.tasks.get(task.task_id)
        if not task_record:
            return

        task_record.status = TaskStatus.RUNNING
        task_record.assigned_peer = settings.node_id
        task_record.updated_at = datetime.utcnow()

        try:
            result = await self.role_manager.execute_task(task.role, task)

            task_record.status = TaskStatus.COMPLETED if result["success"] else TaskStatus.FAILED
            task_record.result = result.get("result", "")
            task_record.error = result.get("error")
            task_record.updated_at = datetime.utcnow()

            if task.task_id in self.pending_results:
                future = self.pending_results[task.task_id]
                if not future.done():
                    future.set_result(result)

            logger.info(f"Completed local task {task.task_id}")

        except Exception as e:
            logger.error(f"Error executing task {task.task_id}: {e}")
            task_record.status = TaskStatus.FAILED
            task_record.error = str(e)
            task_record.updated_at = datetime.utcnow()

            if task.task_id in self.pending_results:
                future = self.pending_results[task.task_id]
                if not future.done():
                    future.set_exception(e)

    async def _delegate_task(self, task: TaskMessage):
        task_record = self.tasks.get(task.task_id)
        if not task_record:
            return

        best_peer = await self._find_best_peer(task.role)

        if not best_peer:
            logger.warning(f"No peer available for role {task.role}, queuing task {task.task_id}")
            task_record.status = TaskStatus.PENDING
            return

        task_record.status = TaskStatus.ASSIGNED
        task_record.assigned_peer = best_peer.peer_id
        task_record.updated_at = datetime.utcnow()

        message = Message(
            msg_type=MessageType.TASK,
            msg_id=str(uuid.uuid4()),
            sender_id=settings.node_id,
            timestamp=datetime.utcnow(),
            payload=task.model_dump()
        )

        success = await self.ws_server.send_message(best_peer.peer_id, message)

        if not success:
            logger.error(f"Failed to delegate task {task.task_id} to {best_peer.peer_id}")
            task_record.status = TaskStatus.PENDING
            task_record.assigned_peer = None
        else:
            logger.info(f"Delegated task {task.task_id} to {best_peer.peer_id}")

    async def _find_best_peer(self, role: str) -> Optional[PeerInfo]:
        multicast_peers = self.discovery_service.get_peers()
        ws_peers = self.ws_server.peer_registry
        all_peers = {**multicast_peers, **ws_peers}

        suitable_peers = [
            peer for peer in all_peers.values()
            if role in peer.roles
        ]

        if not suitable_peers:
            return None

        suitable_peers.sort(key=lambda p: (p.load, -p.qos))
        return suitable_peers[0]

    async def handle_incoming_task(self, task: TaskMessage, sender_id: str):
        logger.info(f"Received task {task.task_id} from {sender_id}")

        task_record = TaskRecord(
            task_id=task.task_id,
            role=task.role,
            prompt=task.prompt,
            status=TaskStatus.ASSIGNED,
            assigned_peer=settings.node_id
        )
        self.tasks[task.task_id] = task_record

        if self.role_manager.has_role(task.role):
            asyncio.create_task(self._execute_incoming_task(task, sender_id))
        else:
            logger.warning(f"Received task for unavailable role {task.role}")
            task_record.status = TaskStatus.FAILED
            task_record.error = f"Role {task.role} not available"

    async def _execute_incoming_task(self, task: TaskMessage, sender_id: str):
        task_record = self.tasks[task.task_id]
        task_record.status = TaskStatus.RUNNING
        task_record.updated_at = datetime.utcnow()

        try:
            result = await self.role_manager.execute_task(task.role, task)

            task_record.status = TaskStatus.COMPLETED if result["success"] else TaskStatus.FAILED
            task_record.result = result.get("result", "")
            task_record.error = result.get("error")
            task_record.updated_at = datetime.utcnow()

            result_msg = ResultMessage(
                task_id=task.task_id,
                result=result.get("result", ""),
                success=result["success"],
                error=result.get("error"),
                metadata=result.get("metadata", {})
            )

            message = Message(
                msg_type=MessageType.RESULT,
                msg_id=str(uuid.uuid4()),
                sender_id=settings.node_id,
                timestamp=datetime.utcnow(),
                payload=result_msg.model_dump()
            )

            await self.ws_server.send_message(sender_id, message)
            logger.info(f"Sent result for task {task.task_id} to {sender_id}")

        except Exception as e:
            logger.error(f"Error executing incoming task {task.task_id}: {e}")
            task_record.status = TaskStatus.FAILED
            task_record.error = str(e)

    async def handle_task_result(self, result: ResultMessage, sender_id: str):
        logger.info(f"Received result for task {result.task_id} from {sender_id}")

        task_record = self.tasks.get(result.task_id)
        if task_record:
            task_record.status = TaskStatus.COMPLETED if result.success else TaskStatus.FAILED
            task_record.result = result.result
            task_record.error = result.error
            task_record.updated_at = datetime.utcnow()

        if result.task_id in self.pending_results:
            future = self.pending_results[result.task_id]
            if not future.done():
                if result.success:
                    future.set_result({"success": True, "result": result.result, "metadata": result.metadata})
                else:
                    future.set_exception(Exception(result.error or "Task failed"))

    async def wait_for_task(self, task_id: str, timeout: float = 120.0) -> dict:
        if task_id not in self.pending_results:
            self.pending_results[task_id] = asyncio.Future()

        try:
            result = await asyncio.wait_for(self.pending_results[task_id], timeout=timeout)
            return result
        except asyncio.TimeoutError:
            logger.error(f"Task {task_id} timed out")
            raise
        finally:
            if task_id in self.pending_results:
                del self.pending_results[task_id]

    def get_task_status(self, task_id: str) -> Optional[TaskRecord]:
        return self.tasks.get(task_id)

    def get_all_tasks(self) -> List[TaskRecord]:
        return list(self.tasks.values())
