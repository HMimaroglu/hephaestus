from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum


class MessageType(str, Enum):
    HELLO = "HELLO"
    TASK = "TASK"
    RESULT = "RESULT"
    HEARTBEAT = "HEARTBEAT"
    NEGOTIATE = "NEGOTIATE"
    TRANSFER = "TRANSFER"
    ACK = "ACK"
    REGISTER = "REGISTER"
    PEER_LIST = "PEER_LIST"
    RELAY = "RELAY"


class TaskStatus(str, Enum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class RoleType(str, Enum):
    RESEARCHER = "researcher"
    PROGRAMMER = "programmer"
    PRESENTER = "presenter"


class PeerInfo(BaseModel):
    peer_id: str
    ip: str
    port: int
    ws_port: int
    roles: List[str] = Field(default_factory=list)
    load: float = Field(default=0.0, ge=0.0, le=1.0)
    qos: float = Field(default=1.0, ge=0.0, le=1.0)
    last_seen: datetime = Field(default_factory=datetime.utcnow)


class Message(BaseModel):
    msg_type: MessageType
    msg_id: str
    sender_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    payload: Dict[str, Any] = Field(default_factory=dict)


class HelloMessage(BaseModel):
    peer_id: str
    ip: str
    port: int
    ws_port: int
    roles: List[str]
    load: float
    qos: float


class TaskMessage(BaseModel):
    task_id: str
    role: str
    prompt: str
    context: Dict[str, Any] = Field(default_factory=dict)
    priority: int = Field(default=1, ge=1, le=10)
    timeout: int = Field(default=120)


class ResultMessage(BaseModel):
    task_id: str
    result: str
    success: bool
    error: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class HeartbeatMessage(BaseModel):
    load: float
    qos: float
    active_tasks: int
    roles: List[str]


class NegotiateMessage(BaseModel):
    role: str
    reason: str
    target_peer_id: Optional[str] = None
    load_threshold: float


class TransferMessage(BaseModel):
    role: str
    state: Dict[str, Any]
    task_queue: List[Dict[str, Any]] = Field(default_factory=list)


class RegisterMessage(BaseModel):
    peer_id: str
    ip: str
    port: int
    ws_port: int
    roles: List[str]
    load: float
    qos: float


class PeerListMessage(BaseModel):
    peers: List[PeerInfo]


class RelayMessage(BaseModel):
    target_peer_id: str
    original_message: Dict[str, Any]


class TaskRecord(BaseModel):
    task_id: str
    role: str
    prompt: str
    status: TaskStatus
    assigned_peer: Optional[str] = None
    result: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    error: Optional[str] = None


class NodeHealth(BaseModel):
    node_id: str
    node_name: str
    uptime: float
    cpu_percent: float
    memory_percent: float
    active_roles: List[str]
    active_tasks: int
    peer_count: int
    load: float
    qos: float
