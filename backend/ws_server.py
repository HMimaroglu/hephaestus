import asyncio
import json
import logging
import uuid
from datetime import datetime
from typing import Dict, Set, Optional
import websockets
from websockets.server import WebSocketServerProtocol
from backend.settings import settings
from backend.schemas import (
    Message, MessageType, TaskMessage, ResultMessage,
    HeartbeatMessage, NegotiateMessage, TransferMessage,
    RegisterMessage, PeerListMessage, RelayMessage, PeerInfo
)

logger = logging.getLogger(__name__)


class WebSocketServer:

    def __init__(self, router=None, role_manager=None):
        self.router = router
        self.role_manager = role_manager
        self.connections: Dict[str, WebSocketServerProtocol] = {}
        self.running = False
        self.server: Optional[websockets.WebSocketServer] = None
        self.peer_registry: Dict[str, PeerInfo] = {}
        self.message_handlers: Dict[MessageType, callable] = {
            MessageType.TASK: self._handle_task,
            MessageType.RESULT: self._handle_result,
            MessageType.HEARTBEAT: self._handle_heartbeat,
            MessageType.NEGOTIATE: self._handle_negotiate,
            MessageType.TRANSFER: self._handle_transfer,
            MessageType.REGISTER: self._handle_register,
            MessageType.PEER_LIST: self._handle_peer_list,
            MessageType.RELAY: self._handle_relay,
        }

    async def start(self):
        self.running = True
        self.server = await websockets.serve(
            self._handle_connection,
            settings.host,
            settings.ws_port
        )
        logger.info(f"WebSocket server started on {settings.host}:{settings.ws_port}")

    async def stop(self):
        self.running = False
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        for ws in list(self.connections.values()):
            await ws.close()
        self.connections.clear()
        logger.info("WebSocket server stopped")

    async def _handle_connection(self, websocket):
        peer_id = None
        try:
            async for raw_message in websocket:
                try:
                    data = json.loads(raw_message)
                    message = Message(**data)

                    if peer_id is None:
                        peer_id = message.sender_id
                        self.connections[peer_id] = websocket
                        logger.info(f"WebSocket connection established with {peer_id}")

                    await self._route_message(message)

                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON received: {e}")
                except Exception as e:
                    logger.error(f"Error processing message: {e}")

        except websockets.exceptions.ConnectionClosed:
            logger.info(f"WebSocket connection closed for {peer_id}")
        finally:
            if peer_id:
                if peer_id in self.connections:
                    del self.connections[peer_id]
                if peer_id in self.peer_registry:
                    del self.peer_registry[peer_id]
                    logger.info(f"Removed peer {peer_id} from registry")

    async def _route_message(self, message: Message):
        handler = self.message_handlers.get(message.msg_type)
        if handler:
            await handler(message)
        else:
            logger.warning(f"No handler for message type: {message.msg_type}")

    async def _handle_task(self, message: Message):
        try:
            task_msg = TaskMessage(**message.payload)
            logger.info(f"Received TASK {task_msg.task_id} from {message.sender_id}")

            if self.router:
                await self.router.handle_incoming_task(task_msg, message.sender_id)

            ack = Message(
                msg_type=MessageType.ACK,
                msg_id=str(uuid.uuid4()),
                sender_id=settings.node_id,
                payload={"task_id": task_msg.task_id, "status": "received"}
            )
            await self.send_message(message.sender_id, ack)

        except Exception as e:
            logger.error(f"Error handling TASK message: {e}")

    async def _handle_result(self, message: Message):
        try:
            result_msg = ResultMessage(**message.payload)
            logger.info(f"Received RESULT for task {result_msg.task_id} from {message.sender_id}")

            if self.router:
                await self.router.handle_task_result(result_msg, message.sender_id)

        except Exception as e:
            logger.error(f"Error handling RESULT message: {e}")

    async def _handle_heartbeat(self, message: Message):
        try:
            heartbeat = HeartbeatMessage(**message.payload)
            logger.debug(f"Received HEARTBEAT from {message.sender_id}")

        except Exception as e:
            logger.error(f"Error handling HEARTBEAT message: {e}")

    async def _handle_negotiate(self, message: Message):
        try:
            negotiate = NegotiateMessage(**message.payload)
            logger.info(f"Received NEGOTIATE from {message.sender_id}: {negotiate.reason}")

            if self.role_manager:
                await self.role_manager.handle_negotiate(negotiate, message.sender_id)

        except Exception as e:
            logger.error(f"Error handling NEGOTIATE message: {e}")

    async def _handle_transfer(self, message: Message):
        try:
            transfer = TransferMessage(**message.payload)
            logger.info(f"Received TRANSFER for role {transfer.role} from {message.sender_id}")

            if self.role_manager:
                await self.role_manager.handle_transfer(transfer, message.sender_id)

        except Exception as e:
            logger.error(f"Error handling TRANSFER message: {e}")

    async def _handle_register(self, message: Message):
        try:
            register = RegisterMessage(**message.payload)
            logger.info(f"Received REGISTER from {register.peer_id}")

            peer_info = PeerInfo(
                peer_id=register.peer_id,
                ip=register.ip,
                port=register.port,
                ws_port=register.ws_port,
                roles=register.roles,
                load=register.load,
                qos=register.qos,
                last_seen=datetime.utcnow()
            )

            self.peer_registry[register.peer_id] = peer_info

            if settings.is_seed_node:
                await self._broadcast_peer_list()

        except Exception as e:
            logger.error(f"Error handling REGISTER message: {e}")

    async def _handle_peer_list(self, message: Message):
        try:
            peer_list = PeerListMessage(**message.payload)
            logger.info(f"Received PEER_LIST with {len(peer_list.peers)} peers from {message.sender_id}")

            seed_conn_key = None
            for key in list(self.connections.keys()):
                if key.startswith("seed-"):
                    seed_conn_key = key
                    break

            if seed_conn_key and message.sender_id != settings.node_id:
                websocket = self.connections.pop(seed_conn_key)
                self.connections[message.sender_id] = websocket
                logger.info(f"Updated seed connection key from {seed_conn_key} to {message.sender_id}")

            for peer_info in peer_list.peers:
                if peer_info.peer_id != settings.node_id:
                    self.peer_registry[peer_info.peer_id] = peer_info
                    if peer_info.peer_id not in self.connections:
                        asyncio.create_task(self.connect_to_peer(
                            peer_info.peer_id,
                            peer_info.ip,
                            peer_info.ws_port
                        ))

        except Exception as e:
            logger.error(f"Error handling PEER_LIST message: {e}")

    async def _handle_relay(self, message: Message):
        try:
            relay = RelayMessage(**message.payload)
            logger.info(f"Received RELAY for {relay.target_peer_id} from {message.sender_id}")

            target_ws = self.connections.get(relay.target_peer_id)
            if target_ws:
                relayed_message = Message(**relay.original_message)
                await self.send_message(relay.target_peer_id, relayed_message)
            else:
                logger.warning(f"Cannot relay to {relay.target_peer_id}: not connected")

        except Exception as e:
            logger.error(f"Error handling RELAY message: {e}")

    async def send_message(self, peer_id: str, message: Message) -> bool:
        websocket = self.connections.get(peer_id)
        if not websocket:
            logger.warning(f"No WebSocket connection for peer {peer_id}")
            return False

        try:
            data = json.dumps(message.model_dump(mode='json'))
            await websocket.send(data)
            logger.debug(f"Sent {message.msg_type} to {peer_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to send message to {peer_id}: {e}")
            return False

    async def broadcast_message(self, message: Message, exclude: Optional[Set[str]] = None):
        exclude = exclude or set()
        for peer_id in list(self.connections.keys()):
            if peer_id not in exclude:
                await self.send_message(peer_id, message)

    async def connect_to_peer(self, peer_id: str, peer_ip: str, peer_ws_port: int) -> Optional[str]:
        if peer_id in self.connections:
            logger.debug(f"Already connected to peer {peer_id}")
            return peer_id

        uri = f"ws://{peer_ip}:{peer_ws_port}"
        try:
            websocket = await websockets.connect(uri)
            self.connections[peer_id] = websocket

            asyncio.create_task(self._handle_outbound_connection(websocket, peer_id))

            logger.info(f"Connected to peer {peer_id} at {uri}")
            return peer_id
        except Exception as e:
            logger.error(f"Failed to connect to peer at {uri}: {e}")
            return None

    async def _handle_outbound_connection(self, websocket, peer_id: str):
        try:
            async for raw_message in websocket:
                try:
                    data = json.loads(raw_message)
                    message = Message(**data)
                    await self._route_message(message)
                except Exception as e:
                    logger.error(f"Error processing message from {peer_id}: {e}")
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"Outbound connection to {peer_id} closed")
        except Exception as e:
            logger.error(f"Error in outbound connection to {peer_id}: {e}")
        finally:
            if peer_id in self.connections:
                del self.connections[peer_id]
            if peer_id in self.peer_registry:
                del self.peer_registry[peer_id]
                logger.info(f"Removed peer {peer_id} from registry")

    async def connect_to_seed(self, seed_url: str) -> Optional[str]:
        try:
            websocket = await websockets.connect(seed_url)
            logger.info(f"Connected to seed node at {seed_url}")

            import psutil
            roles = self.role_manager.get_active_roles() if self.role_manager else []
            load = psutil.cpu_percent(interval=0.1) / 100.0
            qos = 1.0 - load

            register_msg = Message(
                msg_type=MessageType.REGISTER,
                msg_id=str(uuid.uuid4()),
                sender_id=settings.node_id,
                payload=RegisterMessage(
                    peer_id=settings.node_id,
                    ip=self._get_local_ip(),
                    port=settings.port,
                    ws_port=settings.ws_port,
                    roles=roles,
                    load=load,
                    qos=qos
                ).model_dump()
            )

            await websocket.send(json.dumps(register_msg.model_dump(mode='json')))

            seed_peer_id = f"seed-{seed_url}"
            self.connections[seed_peer_id] = websocket

            asyncio.create_task(self._handle_outbound_connection(websocket, seed_peer_id))

            return seed_peer_id
        except Exception as e:
            logger.error(f"Failed to connect to seed at {seed_url}: {e}")
            return None

    async def _broadcast_peer_list(self):
        import psutil
        self_info = PeerInfo(
            peer_id=settings.node_id,
            ip=self._get_local_ip(),
            port=settings.port,
            ws_port=settings.ws_port,
            roles=self.role_manager.get_active_roles() if self.role_manager else [],
            load=psutil.cpu_percent(interval=0.1) / 100.0,
            qos=1.0 - (psutil.cpu_percent(interval=0.1) / 100.0),
            last_seen=datetime.utcnow()
        )

        all_peers = [self_info] + list(self.peer_registry.values())

        peer_list_msg = Message(
            msg_type=MessageType.PEER_LIST,
            msg_id=str(uuid.uuid4()),
            sender_id=settings.node_id,
            payload=PeerListMessage(
                peers=all_peers
            ).model_dump(mode='json')
        )

        for peer_id in list(self.connections.keys()):
            await self.send_message(peer_id, peer_list_msg)

    def _get_local_ip(self) -> str:
        if settings.public_ip:
            return settings.public_ip
        try:
            import socket
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"
