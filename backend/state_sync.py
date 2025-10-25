import asyncio
import logging
import json
from typing import Dict, Any, Optional
from datetime import datetime
from backend.settings import settings

logger = logging.getLogger(__name__)


class StateSyncService:

    def __init__(self, role_manager=None, ws_server=None):
        self.role_manager = role_manager
        self.ws_server = ws_server
        self.sync_interval = 60
        self.running = False
        self._sync_task: Optional[asyncio.Task] = None

    async def start(self):
        self.running = True
        self._sync_task = asyncio.create_task(self._sync_loop())
        logger.info("State sync service started")

    async def stop(self):
        self.running = False
        if self._sync_task:
            self._sync_task.cancel()
        logger.info("State sync service stopped")

    async def _sync_loop(self):
        while self.running:
            try:
                await asyncio.sleep(self.sync_interval)
                await self._perform_sync()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in sync loop: {e}")

    async def _perform_sync(self):
        if not self.role_manager:
            return

        roles = self.role_manager.get_active_roles()

        for role_name in roles:
            try:
                state = await self.role_manager.get_role_state(role_name)
                await self._save_state_checkpoint(role_name, state)
            except Exception as e:
                logger.error(f"Error syncing state for role {role_name}: {e}")

        logger.debug("State sync completed")

    async def _save_state_checkpoint(self, role_name: str, state: Dict[str, Any]):
        checkpoint = {
            "role": role_name,
            "node_id": settings.node_id,
            "timestamp": datetime.utcnow().isoformat(),
            "state": state
        }

        try:
            filename = f".hephaestus_state_{role_name}.json"
            with open(filename, 'w') as f:
                json.dump(checkpoint, f, indent=2)
            logger.debug(f"Saved state checkpoint for {role_name}")
        except Exception as e:
            logger.error(f"Failed to save state checkpoint: {e}")

    async def restore_state(self, role_name: str) -> bool:
        try:
            filename = f".hephaestus_state_{role_name}.json"
            with open(filename, 'r') as f:
                checkpoint = json.load(f)

            if checkpoint["role"] != role_name:
                logger.warning(f"Role mismatch in checkpoint: expected {role_name}, got {checkpoint['role']}")
                return False

            state = checkpoint["state"]
            await self.role_manager.restore_state(role_name, state)

            logger.info(f"Restored state for {role_name} from checkpoint")
            return True

        except FileNotFoundError:
            logger.debug(f"No state checkpoint found for {role_name}")
            return False
        except Exception as e:
            logger.error(f"Failed to restore state: {e}")
            return False

    async def sync_state_to_peer(self, peer_id: str, role_name: str) -> bool:
        if not self.role_manager or not self.ws_server:
            return False

        try:
            state = await self.role_manager.get_role_state(role_name)

            from backend.schemas import Message, MessageType, TransferMessage
            import uuid

            transfer = TransferMessage(
                role=role_name,
                state=state,
                task_queue=[]
            )

            message = Message(
                msg_type=MessageType.TRANSFER,
                msg_id=str(uuid.uuid4()),
                sender_id=settings.node_id,
                timestamp=datetime.utcnow(),
                payload=transfer.model_dump()
            )

            success = await self.ws_server.send_message(peer_id, message)
            if success:
                logger.info(f"Synced state for {role_name} to {peer_id}")
            return success

        except Exception as e:
            logger.error(f"Failed to sync state to peer: {e}")
            return False

    def get_checkpoint_info(self, role_name: str) -> Optional[Dict[str, Any]]:
        try:
            filename = f".hephaestus_state_{role_name}.json"
            with open(filename, 'r') as f:
                checkpoint = json.load(f)

            return {
                "role": checkpoint["role"],
                "node_id": checkpoint["node_id"],
                "timestamp": checkpoint["timestamp"],
                "state_size": len(json.dumps(checkpoint["state"]))
            }
        except Exception:
            return None
