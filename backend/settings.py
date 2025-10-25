import os
import uuid
from typing import List
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    node_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    node_name: str = Field(default="hephaestus-node")

    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)

    discovery_port: int = Field(default=9000)
    discovery_multicast_group: str = Field(default="224.0.0.251")
    discovery_multicast_ttl: int = Field(default=2)
    discovery_interval: int = Field(default=5)
    peer_timeout: int = Field(default=30)

    ws_port: int = Field(default=8001)

    is_seed_node: bool = Field(default=False)
    seed_node_url: str = Field(default="")
    public_ip: str = Field(default="")

    initial_roles: List[str] = Field(default_factory=lambda: ["researcher"])
    max_load_threshold: float = Field(default=0.8)
    min_qos_threshold: float = Field(default=0.5)

    llm_backend: str = Field(default="ollama")
    llm_model: str = Field(default="llama3.2:3b")
    llm_host: str = Field(default="http://localhost:11434")
    llm_timeout: int = Field(default=120)

    log_level: str = Field(default="INFO")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


settings = Settings()
