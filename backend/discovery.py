import asyncio
import json
import logging
import socket
import struct
from datetime import datetime, timedelta
from typing import Dict, Optional
import psutil
from backend.settings import settings
from backend.schemas import PeerInfo, HelloMessage

logger = logging.getLogger(__name__)


class DiscoveryService:

    def __init__(self, role_manager=None, ws_server=None):
        self.peers: Dict[str, PeerInfo] = {}
        self.role_manager = role_manager
        self.ws_server = ws_server
        self.running = False
        self.sock: Optional[socket.socket] = None
        self._broadcast_task: Optional[asyncio.Task] = None
        self._listen_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None

    async def start(self):
        self.running = True
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        if hasattr(socket, 'SO_REUSEPORT'):
            try:
                self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
                logger.debug("SO_REUSEPORT enabled")
            except (OSError, AttributeError) as e:
                logger.debug(f"Could not enable SO_REUSEPORT: {e}")

        self.sock.setblocking(False)

        try:
            self.sock.bind(("", settings.discovery_port))
            logger.info(f"Discovery service bound to port {settings.discovery_port}")

            mreq = struct.pack("4sl", socket.inet_aton(settings.discovery_multicast_group), socket.INADDR_ANY)
            self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
            self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, settings.discovery_multicast_ttl)
            self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, 1)

            logger.info(f"Joined multicast group {settings.discovery_multicast_group}")
        except OSError as e:
            logger.error(f"Failed to bind discovery port or join multicast group: {e}")
            raise

        self._broadcast_task = asyncio.create_task(self._broadcast_loop())
        self._listen_task = asyncio.create_task(self._listen_loop())
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())

        if settings.seed_node_url and self.ws_server:
            asyncio.create_task(self._connect_to_seed_node())

        logger.info("Discovery service started")

    async def stop(self):
        self.running = False

        if self._broadcast_task:
            self._broadcast_task.cancel()
        if self._listen_task:
            self._listen_task.cancel()
        if self._cleanup_task:
            self._cleanup_task.cancel()

        if self.sock:
            self.sock.close()

        logger.info("Discovery service stopped")

    async def _broadcast_loop(self):
        while self.running:
            try:
                await self._broadcast_hello()
                await asyncio.sleep(settings.discovery_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in broadcast loop: {e}")
                await asyncio.sleep(1)

    async def _broadcast_hello(self):
        roles = self.role_manager.get_active_roles() if self.role_manager else []
        load = psutil.cpu_percent(interval=0.1) / 100.0
        qos = 1.0 - load

        hello = HelloMessage(
            peer_id=settings.node_id,
            ip=self._get_local_ip(),
            port=settings.port,
            ws_port=settings.ws_port,
            roles=roles,
            load=load,
            qos=qos
        )

        message = json.dumps(hello.model_dump())

        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                self.sock.sendto,
                message.encode(),
                (settings.discovery_multicast_group, settings.discovery_port)
            )
            logger.debug(f"Multicast HELLO: {hello.peer_id}")
        except Exception as e:
            logger.error(f"Failed to multicast HELLO: {e}")

    async def _listen_loop(self):
        loop = asyncio.get_event_loop()

        while self.running:
            try:
                data, addr = await loop.run_in_executor(
                    None,
                    self.sock.recvfrom,
                    4096
                )
                await self._handle_message(data, addr)
            except asyncio.CancelledError:
                break
            except BlockingIOError:
                await asyncio.sleep(0.1)
            except Exception as e:
                logger.error(f"Error in listen loop: {e}")
                await asyncio.sleep(0.1)

    async def _handle_message(self, data: bytes, addr: tuple):
        try:
            message = json.loads(data.decode())
            hello = HelloMessage(**message)

            if hello.peer_id == settings.node_id:
                return

            peer_info = PeerInfo(
                peer_id=hello.peer_id,
                ip=hello.ip,
                port=hello.port,
                ws_port=hello.ws_port,
                roles=hello.roles,
                load=hello.load,
                qos=hello.qos,
                last_seen=datetime.utcnow()
            )

            is_new_peer = hello.peer_id not in self.peers

            if is_new_peer:
                logger.info(f"New peer discovered: {hello.peer_id} at {hello.ip}:{hello.port}")

            self.peers[hello.peer_id] = peer_info

            if is_new_peer and self.ws_server:
                asyncio.create_task(self._connect_to_peer(hello.peer_id, hello.ip, hello.ws_port))

        except json.JSONDecodeError as e:
            logger.warning(f"Invalid JSON from {addr}: {e}")
        except Exception as e:
            logger.error(f"Error handling message from {addr}: {e}")

    async def _cleanup_loop(self):
        while self.running:
            try:
                await asyncio.sleep(10)
                await self._cleanup_stale_peers()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")

    async def _cleanup_stale_peers(self):
        now = datetime.utcnow()
        timeout = timedelta(seconds=settings.peer_timeout)
        stale_peers = []

        for peer_id, peer in self.peers.items():
            if now - peer.last_seen > timeout:
                stale_peers.append(peer_id)

        for peer_id in stale_peers:
            logger.info(f"Removing stale peer: {peer_id}")
            del self.peers[peer_id]

    def get_peers(self) -> Dict[str, PeerInfo]:
        return self.peers.copy()

    def get_peer(self, peer_id: str) -> Optional[PeerInfo]:
        return self.peers.get(peer_id)

    async def _connect_to_peer(self, peer_id: str, peer_ip: str, peer_ws_port: int):
        try:
            await asyncio.sleep(0.5)
            connected_peer_id = await self.ws_server.connect_to_peer(peer_id, peer_ip, peer_ws_port)
            if connected_peer_id:
                logger.info(f"Established WebSocket connection to peer {peer_id}")
            else:
                logger.warning(f"Failed to establish WebSocket connection to peer {peer_id}")
        except Exception as e:
            logger.error(f"Error connecting to peer {peer_id}: {e}")

    def _get_local_ip(self) -> str:
        if settings.public_ip:
            return settings.public_ip
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    async def _connect_to_seed_node(self):
        try:
            await asyncio.sleep(1)
            logger.info(f"Connecting to seed node: {settings.seed_node_url}")

            seed_peer_id = await self.ws_server.connect_to_seed(settings.seed_node_url)

            if seed_peer_id:
                logger.info(f"Connected to seed node: {seed_peer_id}")
            else:
                logger.error("Failed to connect to seed node")
        except Exception as e:
            logger.error(f"Error connecting to seed node: {e}")
