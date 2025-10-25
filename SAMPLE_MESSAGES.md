# Sample Message Payloads

This document provides sample JSON payloads for each message type in the Hephaestus mesh network.

## HELLO Message (UDP Discovery)

Broadcast message sent periodically to discover peers on the LAN.

```json
{
  "peer_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "ip": "192.168.1.100",
  "port": 8000,
  "ws_port": 8001,
  "roles": ["researcher", "programmer"],
  "load": 0.35,
  "qos": 0.65
}
```

## TASK Message (WebSocket)

Sent to delegate a task to another node.

```json
{
  "msg_type": "TASK",
  "msg_id": "task-msg-12345",
  "sender_id": "node-alpha-uuid",
  "timestamp": "2025-01-15T10:30:00.000Z",
  "payload": {
    "task_id": "task-uuid-67890",
    "role": "researcher",
    "prompt": "Analyze the impact of quantum computing on cryptography",
    "context": {
      "domain": "cryptography",
      "depth": "detailed"
    },
    "priority": 2,
    "timeout": 120
  }
}
```

## RESULT Message (WebSocket)

Sent back after completing a task.

```json
{
  "msg_type": "RESULT",
  "msg_id": "result-msg-54321",
  "sender_id": "node-beta-uuid",
  "timestamp": "2025-01-15T10:32:30.000Z",
  "payload": {
    "task_id": "task-uuid-67890",
    "result": "Quantum computing poses a significant threat to current cryptographic systems...",
    "success": true,
    "error": null,
    "metadata": {
      "role": "researcher",
      "execution_time": 145.3,
      "tokens_used": 1250
    }
  }
}
```

## HEARTBEAT Message (WebSocket)

Periodic status update sent between connected peers.

```json
{
  "msg_type": "HEARTBEAT",
  "msg_id": "heartbeat-msg-99999",
  "sender_id": "node-gamma-uuid",
  "timestamp": "2025-01-15T10:33:00.000Z",
  "payload": {
    "load": 0.42,
    "qos": 0.58,
    "active_tasks": 3,
    "roles": ["programmer", "presenter"]
  }
}
```

## NEGOTIATE Message (WebSocket)

Sent when a node is overloaded and wants to transfer a role.

```json
{
  "msg_type": "NEGOTIATE",
  "msg_id": "negotiate-msg-11111",
  "sender_id": "node-delta-uuid",
  "timestamp": "2025-01-15T10:35:00.000Z",
  "payload": {
    "role": "programmer",
    "reason": "overload",
    "target_peer_id": null,
    "load_threshold": 0.85
  }
}
```

Alternative with specific target:

```json
{
  "msg_type": "NEGOTIATE",
  "msg_id": "negotiate-msg-22222",
  "sender_id": "node-delta-uuid",
  "timestamp": "2025-01-15T10:35:30.000Z",
  "payload": {
    "role": "programmer",
    "reason": "failover",
    "target_peer_id": "node-epsilon-uuid",
    "load_threshold": 0.90
  }
}
```

## TRANSFER Message (WebSocket)

Sent to transfer a role's state to another node.

```json
{
  "msg_type": "TRANSFER",
  "msg_id": "transfer-msg-33333",
  "sender_id": "node-delta-uuid",
  "timestamp": "2025-01-15T10:36:00.000Z",
  "payload": {
    "role": "programmer",
    "state": {
      "code_history": [
        {
          "task_id": "task-abc-123",
          "prompt": "Write a sorting algorithm",
          "result": "def quicksort(arr): ..."
        }
      ],
      "language_stats": {
        "python": 15,
        "javascript": 8
      }
    },
    "task_queue": [
      {
        "task_id": "task-def-456",
        "role": "programmer",
        "prompt": "Implement binary search",
        "priority": 1
      }
    ]
  }
}
```

## ACK Message (WebSocket)

Acknowledgment message sent after receiving a task or other important message.

```json
{
  "msg_type": "ACK",
  "msg_id": "ack-msg-44444",
  "sender_id": "node-beta-uuid",
  "timestamp": "2025-01-15T10:30:01.000Z",
  "payload": {
    "task_id": "task-uuid-67890",
    "status": "received"
  }
}
```

## REST API Payloads

### Submit Task (POST /tasks)

```json
{
  "role": "researcher",
  "prompt": "What are the key principles of distributed systems?",
  "context": {
    "focus": "CAP theorem"
  },
  "priority": 1
}
```

Response:

```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "submitted"
}
```

### Health Check (GET /health)

Response:

```json
{
  "node_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "node_name": "hephaestus-node",
  "uptime": 3600.5,
  "cpu_percent": 35.2,
  "memory_percent": 42.8,
  "active_roles": ["researcher", "programmer"],
  "active_tasks": 2,
  "peer_count": 3,
  "load": 0.39,
  "qos": 0.61
}
```

### List Peers (GET /peers)

Response:

```json
[
  {
    "peer_id": "peer-1-uuid",
    "ip": "192.168.1.101",
    "port": 8000,
    "ws_port": 8001,
    "roles": ["researcher"],
    "load": 0.25,
    "qos": 0.75,
    "last_seen": "2025-01-15T10:37:00.000Z"
  },
  {
    "peer_id": "peer-2-uuid",
    "ip": "192.168.1.102",
    "port": 8100,
    "ws_port": 8101,
    "roles": ["programmer", "presenter"],
    "load": 0.45,
    "qos": 0.55,
    "last_seen": "2025-01-15T10:37:02.000Z"
  }
]
```

### Task Status (GET /tasks/{task_id})

Response:

```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "role": "researcher",
  "prompt": "What are the key principles of distributed systems?",
  "status": "completed",
  "assigned_peer": "node-beta-uuid",
  "result": "The key principles of distributed systems include: 1) No shared state...",
  "created_at": "2025-01-15T10:30:00.000Z",
  "updated_at": "2025-01-15T10:32:15.000Z",
  "error": null
}
```
