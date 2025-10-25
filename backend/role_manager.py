import asyncio
import logging
import importlib
from typing import Dict, List, Optional, Any
import psutil
from backend.settings import settings
from backend.schemas import NegotiateMessage, TransferMessage, TaskMessage

logger = logging.getLogger(__name__)


class RoleManager:

    def __init__(self):
        self.roles: Dict[str, Any] = {}
        self.active_tasks: Dict[str, int] = {}
        self.role_classes = {
            "researcher": "backend.roles.researcher.ResearcherRole",
            "programmer": "backend.roles.programmer.ProgrammerRole",
            "presenter": "backend.roles.presenter.PresenterRole"
        }

    async def initialize(self):
        for role_name in settings.initial_roles:
            await self.add_role(role_name)
        logger.info(f"Initialized roles: {list(self.roles.keys())}")

    async def add_role(self, role_name: str) -> bool:
        if role_name in self.roles:
            logger.warning(f"Role {role_name} already exists")
            return False

        try:
            role_class_path = self.role_classes.get(role_name)
            if not role_class_path:
                logger.error(f"Unknown role: {role_name}")
                return False

            module_path, class_name = role_class_path.rsplit(".", 1)
            module = importlib.import_module(module_path)
            role_class = getattr(module, class_name)

            role_instance = role_class()
            await role_instance.initialize()

            self.roles[role_name] = role_instance
            self.active_tasks[role_name] = 0

            logger.info(f"Added role: {role_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to add role {role_name}: {e}")
            return False

    async def remove_role(self, role_name: str) -> bool:
        if role_name not in self.roles:
            logger.warning(f"Role {role_name} does not exist")
            return False

        try:
            role = self.roles[role_name]
            await role.cleanup()

            del self.roles[role_name]
            del self.active_tasks[role_name]

            logger.info(f"Removed role: {role_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to remove role {role_name}: {e}")
            return False

    async def execute_task(self, role_name: str, task: TaskMessage) -> dict:
        if role_name not in self.roles:
            raise ValueError(f"Role {role_name} not available")

        role = self.roles[role_name]
        self.active_tasks[role_name] += 1

        try:
            logger.info(f"Executing task {task.task_id} with role {role_name}")
            result = await role.execute(task)
            return result
        finally:
            self.active_tasks[role_name] -= 1

    def get_active_roles(self) -> List[str]:
        return list(self.roles.keys())

    def has_role(self, role_name: str) -> bool:
        return role_name in self.roles

    def get_load(self) -> float:
        cpu = psutil.cpu_percent(interval=0.1) / 100.0
        mem = psutil.virtual_memory().percent / 100.0
        task_load = sum(self.active_tasks.values()) / max(len(self.roles) * 5, 1)
        return min((cpu + mem + task_load) / 3.0, 1.0)

    def get_qos(self) -> float:
        return max(1.0 - self.get_load(), 0.0)

    async def check_load_and_negotiate(self, ws_server) -> None:
        load = self.get_load()

        if load > settings.max_load_threshold:
            logger.warning(f"Node overloaded: {load:.2f}")
            await self._negotiate_offload(ws_server)

    async def _negotiate_offload(self, ws_server) -> None:
        if not self.roles:
            return

        role_to_offload = max(self.active_tasks.items(), key=lambda x: x[1])[0]

        negotiate_msg = NegotiateMessage(
            role=role_to_offload,
            reason="overload",
            load_threshold=self.get_load()
        )

        from backend.schemas import Message, MessageType
        import uuid
        from datetime import datetime

        message = Message(
            msg_type=MessageType.NEGOTIATE,
            msg_id=str(uuid.uuid4()),
            sender_id=settings.node_id,
            timestamp=datetime.utcnow(),
            payload=negotiate_msg.model_dump()
        )

        await ws_server.broadcast_message(message)
        logger.info(f"Broadcast NEGOTIATE for role {role_to_offload}")

    async def handle_negotiate(self, negotiate: NegotiateMessage, sender_id: str):
        logger.info(f"Received NEGOTIATE from {sender_id} for role {negotiate.role}")

        my_load = self.get_load()
        if my_load < settings.min_qos_threshold and not self.has_role(negotiate.role):
            logger.info(f"Accepting role {negotiate.role} from {sender_id}")
            await self.add_role(negotiate.role)

    async def handle_transfer(self, transfer: TransferMessage, sender_id: str):
        logger.info(f"Received TRANSFER for role {transfer.role} from {sender_id}")

        if not self.has_role(transfer.role):
            await self.add_role(transfer.role)

        if transfer.role in self.roles:
            role = self.roles[transfer.role]
            await role.restore_state(transfer.state)
            logger.info(f"Restored state for role {transfer.role}")

    async def get_role_state(self, role_name: str) -> Dict[str, Any]:
        if role_name not in self.roles:
            return {}

        role = self.roles[role_name]
        return await role.get_state()

    async def transfer_role(self, role_name: str, target_peer_id: str, ws_server) -> bool:
        if role_name not in self.roles:
            logger.error(f"Cannot transfer non-existent role: {role_name}")
            return False

        try:
            state = await self.get_role_state(role_name)

            transfer_msg = TransferMessage(
                role=role_name,
                state=state,
                task_queue=[]
            )

            from backend.schemas import Message, MessageType
            import uuid
            from datetime import datetime

            message = Message(
                msg_type=MessageType.TRANSFER,
                msg_id=str(uuid.uuid4()),
                sender_id=settings.node_id,
                timestamp=datetime.utcnow(),
                payload=transfer_msg.model_dump()
            )

            success = await ws_server.send_message(target_peer_id, message)

            if success:
                await self.remove_role(role_name)
                logger.info(f"Transferred role {role_name} to {target_peer_id}")
                return True
            else:
                logger.error(f"Failed to send TRANSFER message to {target_peer_id}")
                return False

        except Exception as e:
            logger.error(f"Error transferring role {role_name}: {e}")
            return False
