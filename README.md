# Hephaestus - Adaptive Offline AI Mesh

Hephaestus is a distributed AI mesh network where nodes discover each other via UDP, communicate via WebSockets, and collaboratively process tasks using local LLM models. Each node can dynamically clone or swap AI roles based on load, creating a resilient, self-organizing system.

## Features

- **Peer Discovery**: UDP broadcast-based LAN discovery
- **WebSocket Control Plane**: Real-time communication between nodes
- **Dynamic Role Management**: Nodes can run researcher, programmer, or presenter roles
- **Load Balancing**: Automatic role migration when nodes are overloaded
- **State Synchronization**: Role state can be transferred between nodes
- **Local LLM Integration**: Works with Ollama or llama.cpp
- **Web Dashboard**: Real-time monitoring of peers, tasks, and node health

## Architecture

```
hephaestus/
├── backend/
│   ├── app.py              # Main FastAPI application
│   ├── settings.py         # Configuration management
│   ├── discovery.py        # UDP peer discovery
│   ├── ws_server.py        # WebSocket server
│   ├── router.py           # Task routing logic
│   ├── role_manager.py     # Role lifecycle management
│   ├── state_sync.py       # State synchronization
│   ├── llm.py              # LLM adapter (Ollama/llama.cpp)
│   ├── schemas.py          # Pydantic models
│   └── roles/
│       ├── researcher.py   # Research assistant role
│       ├── programmer.py   # Programming assistant role
│       └── presenter.py    # Presentation assistant role
└── web/
    ├── index.html          # Dashboard UI
    ├── app.js              # Dashboard logic
    └── styles.css          # Dashboard styles
```

## Quick Start

### Quick Start: Offline Mode (Bluetooth or WiFi)

**Want to run a fully offline mesh between two computers? Choose your connection method:**

#### Option A: Bluetooth PAN (Easiest - No Configuration)

**On Both Computers:**

1. **Enable Bluetooth and Pair:**
   - macOS: System Settings → Bluetooth → Turn on Bluetooth
   - Pair the two computers together
   - Once paired, you'll see the other computer in your Bluetooth devices

2. **Connect via Bluetooth PAN:**
   - macOS: Click the Bluetooth icon in menu bar → Click the other computer's name → "Connect to Network"
   - Or: System Settings → Bluetooth → Right-click the paired device → "Connect to Network"
   - Both computers should now be on the same network (typically 172.20.10.x range)

#### Option B: WiFi Hotspot

**On Host Computer:**

   **macOS:**
   - System Settings → General → Sharing → Internet Sharing
   - Share from: (select your internet source)
   - To computers using: Wi-Fi (check the box)
   - Click "Wi-Fi Options" and set network name/password
   - Toggle Internet Sharing ON

   **Windows:**
   - Settings → Network & Internet → Mobile hotspot
   - Turn on "Mobile hotspot"
   - Set network name and password

   **Linux:**
   ```bash
   nmcli dev wifi hotspot ssid HephaestusNet password mypassword123
   ```

**On Client Computer:**
   - Connect to the WiFi hotspot you created

---

**After connecting (either Bluetooth or WiFi):**

3. **On Both Computers - Install and Run:**
   ```bash
   git clone <repository-url>
   cd hephaestus
   pip install -r requirements.txt
   cp .env.hotspot .env

   # Start Ollama (if not already running)
   ollama serve &
   ollama pull llama3.2:3b

   # Run Hephaestus
   python -m backend.app
   ```

4. **Verify:**
   - Open http://localhost:8000 on either computer
   - You should see **1 peer** in the peer count
   - Click to view peers and see the other computer
   - Submit a task with role "researcher"
   - Watch it get processed!

**That's it! Fully offline mesh network with zero internet dependency.**

**Note:** Bluetooth PAN is slower than WiFi but requires zero configuration. Good for 2-3 computers. For larger meshes, use WiFi hotspot or local network.

---

### Prerequisites

1. Python 3.11+
2. Ollama installed and running (or llama.cpp server)

```bash
# Install Ollama (macOS)
brew install ollama

# Start Ollama
ollama serve

# Pull a model
ollama pull llama3.2:3b
```

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd hephaestus

# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.example .env

# Edit .env with your configuration
nano .env
```

### Running a Node

```bash
# Start the first node
python -m backend.app

# In another terminal, start a second node on different ports
# NOTE: Nodes use multicast for discovery, so they share the same discovery port
PORT=8100 WS_PORT=8101 INITIAL_ROLES='["programmer"]' python -m backend.app

# Or use uvicorn directly
uvicorn backend.app:app --host 0.0.0.0 --port 8000
```

### Access the Dashboard

Open your browser to:
- Node 1: http://localhost:8000
- Node 2: http://localhost:8100

The dashboard features:
- **Request/Use Tab**: Submit tasks and view task history with real-time status updates
- **Management Tab**: Monitor node health, active roles, and discovered peers
- Modern UI with Syracuse University color scheme (blue gradient background, orange accents)

## API Endpoints

### Health & Status

- `GET /health` - Node health and metrics
- `GET /peers` - List discovered peers
- `GET /roles` - List active roles
- `GET /tasks` - List all tasks
- `GET /tasks/{task_id}` - Get task status
- `GET /llm/health` - LLM backend health check

### Task Management

- `POST /tasks` - Submit a new task
  ```json
  {
    "role": "researcher",
    "prompt": "Explain quantum computing",
    "priority": 1
  }
  ```

- `GET /tasks/{task_id}/wait` - Wait for task completion

### Role Management

- `POST /roles/{role_name}` - Add a role to the node
- `DELETE /roles/{role_name}` - Remove a role from the node

## Message Types

### HELLO (Discovery)
```json
{
  "peer_id": "uuid",
  "ip": "192.168.1.100",
  "port": 8000,
  "ws_port": 8001,
  "roles": ["researcher"],
  "load": 0.25,
  "qos": 0.75
}
```

### TASK
```json
{
  "msg_type": "TASK",
  "msg_id": "uuid",
  "sender_id": "uuid",
  "timestamp": "2025-01-01T00:00:00",
  "payload": {
    "task_id": "uuid",
    "role": "researcher",
    "prompt": "Research topic",
    "context": {},
    "priority": 1,
    "timeout": 120
  }
}
```

### RESULT
```json
{
  "msg_type": "RESULT",
  "msg_id": "uuid",
  "sender_id": "uuid",
  "timestamp": "2025-01-01T00:00:00",
  "payload": {
    "task_id": "uuid",
    "result": "Task output",
    "success": true,
    "error": null,
    "metadata": {}
  }
}
```

### NEGOTIATE
```json
{
  "msg_type": "NEGOTIATE",
  "msg_id": "uuid",
  "sender_id": "uuid",
  "timestamp": "2025-01-01T00:00:00",
  "payload": {
    "role": "programmer",
    "reason": "overload",
    "target_peer_id": null,
    "load_threshold": 0.85
  }
}
```

### TRANSFER
```json
{
  "msg_type": "TRANSFER",
  "msg_id": "uuid",
  "sender_id": "uuid",
  "timestamp": "2025-01-01T00:00:00",
  "payload": {
    "role": "researcher",
    "state": {"research_history": []},
    "task_queue": []
  }
}
```

## Configuration

Edit `.env` to configure your node:

```env
# Node settings
NODE_NAME=hephaestus-node-1
PORT=8000
WS_PORT=8001

# Discovery
DISCOVERY_PORT=9000
DISCOVERY_INTERVAL=5
PEER_TIMEOUT=30

# Seed Node Configuration (for internet connectivity)
IS_SEED_NODE=false
SEED_NODE_URL=
PUBLIC_IP=

# Initial roles
INITIAL_ROLES=["researcher"]

# Load thresholds
MAX_LOAD_THRESHOLD=0.8
MIN_QOS_THRESHOLD=0.5

# LLM backend
LLM_BACKEND=ollama
LLM_MODEL=llama3.2:3b
LLM_HOST=http://localhost:11434
```

### Network Modes

Hephaestus supports three deployment modes:

**1. Offline WiFi Hotspot (Recommended for Offline Use):**
- Host computer creates WiFi hotspot
- Client devices connect to the hotspot
- Fully offline - no internet required
- Auto-discovery via multicast
- Use `.env.hotspot` configuration
- Perfect for: Remote locations, offline AI collaboration, privacy-focused setups

**2. Local Network (Default):**
- Nodes discover each other via UDP multicast on the same LAN
- All devices on same WiFi/Ethernet network
- No internet connectivity required
- Leave `SEED_NODE_URL` empty

**3. Internet Mode:**
- Connect to a seed node to join a global mesh
- Set `SEED_NODE_URL=ws://your-seed-node.com:8001`
- Nodes can be anywhere on the internet
- Requires deployed seed node (see deployment section)

## Testing

### Test Local Task Execution

```bash
curl -X POST http://localhost:8000/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "role": "researcher",
    "prompt": "What is distributed computing?",
    "priority": 1
  }'
```

### Test Multi-Node Setup

1. Start two nodes on different ports
2. Check peer discovery: `curl http://localhost:8000/peers`
3. Submit a task requiring a role not on node 1
4. Watch it get delegated to node 2

### Test Role Migration

1. Start node 1 with "researcher" role
2. Submit many tasks to overload node 1
3. Start node 2 with low load
4. Node 1 will negotiate and transfer the role to node 2

## Deploying a Seed Node

To host a network that others can join over the internet, deploy a seed node:

### Option 1: Self-Host (Port Forwarding)

1. **Configure your router:**
   - Forward ports 8000 (HTTP) and 8001 (WebSocket) to your computer
   - Find your public IP: `curl ifconfig.me`

2. **Configure the seed node:**
   ```bash
   cp .env.example .env
   nano .env
   ```

   Set these values:
   ```env
   IS_SEED_NODE=true
   PUBLIC_IP=your.public.ip.here
   INITIAL_ROLES=[]  # Seed node doesn't need roles
   ```

3. **Start the seed node:**
   ```bash
   python -m backend.app
   ```

4. **Share the connection URL:**
   - Other nodes connect with: `SEED_NODE_URL=ws://your.public.ip.here:8001`

### Option 2: Cloud Deployment (Recommended)

**Deploy to DigitalOcean, AWS, or any VPS:**

1. **Create a VPS** (1GB RAM minimum)

2. **SSH into the server:**
   ```bash
   ssh root@your-server-ip
   ```

3. **Install dependencies:**
   ```bash
   apt update && apt install -y python3 python3-pip git
   git clone <your-repo-url>
   cd hephaestus
   pip3 install -r requirements.txt
   ```

4. **Configure the seed node:**
   ```bash
   cp .env.example .env
   nano .env
   ```

   Set:
   ```env
   IS_SEED_NODE=true
   PUBLIC_IP=your.server.ip
   HOST=0.0.0.0
   PORT=8000
   WS_PORT=8001
   INITIAL_ROLES=[]
   ```

5. **Run with systemd (persistent):**

   Create `/etc/systemd/system/hephaestus-seed.service`:
   ```ini
   [Unit]
   Description=Hephaestus Seed Node
   After=network.target

   [Service]
   Type=simple
   User=root
   WorkingDirectory=/root/hephaestus
   ExecStart=/usr/bin/python3 -m backend.app
   Restart=always

   [Install]
   WantedBy=multi-user.target
   ```

   Enable and start:
   ```bash
   systemctl enable hephaestus-seed
   systemctl start hephaestus-seed
   systemctl status hephaestus-seed
   ```

6. **Configure firewall:**
   ```bash
   ufw allow 8000/tcp
   ufw allow 8001/tcp
   ufw enable
   ```

### Connecting Client Nodes

Any node can connect to your seed node:

```bash
cp .env.example .env
nano .env
```

Set:
```env
SEED_NODE_URL=ws://your-seed-server.com:8001
# or use IP: ws://123.45.67.89:8001
```

Start the node:
```bash
python -m backend.app
```

The node will:
1. Connect to the seed node
2. Register itself
3. Receive a list of other peers
4. Attempt direct peer connections
5. Fall back to seed relay if needed

## Development

### Project Structure

- **Discovery Service**: UDP broadcast for peer discovery
- **WebSocket Server**: Control plane communication
- **Role Manager**: Lifecycle management for AI roles
- **Task Router**: Intelligent task routing and delegation
- **State Sync**: Periodic state checkpointing and transfer
- **LLM Adapter**: Unified interface for Ollama/llama.cpp

### Adding a New Role

1. Create `backend/roles/your_role.py`
2. Implement the role interface:
   ```python
   class YourRole:
       async def initialize(self): ...
       async def cleanup(self): ...
       async def execute(self, task: TaskMessage) -> dict: ...
       async def get_state(self) -> Dict[str, Any]: ...
       async def restore_state(self, state: Dict[str, Any]): ...
   ```
3. Register in `role_manager.py`

## Troubleshooting

### Nodes not discovering each other

**For WiFi Hotspot Mode:**
- Ensure all devices are connected to the same hotspot WiFi
- On host computer, verify hotspot is active and devices are connected
- Check that firewall allows local network traffic (System Preferences → Security on macOS)
- Try disabling firewall temporarily to test
- Verify all nodes are running on the same `DISCOVERY_PORT` (default: 9000)

**For Local Network Mode:**
- Check firewall settings for UDP port (default: 9000) and multicast traffic
- Ensure nodes are on the same network and multicast is enabled
- Verify multicast group address (default: 224.0.0.251)
- Check `DISCOVERY_PORT` and `DISCOVERY_MULTICAST_GROUP` configuration
- On some networks, multicast may be blocked - contact network admin

**For Internet Mode:**
- Verify `SEED_NODE_URL` is correct and accessible
- Check that seed node is running and listening on correct port
- Ensure firewall allows outbound WebSocket connections

### WebSocket connection failures

- Verify `WS_PORT` is not blocked
- Check for port conflicts
- Review WebSocket server logs

### LLM requests failing

- Ensure Ollama/llama.cpp is running
- Verify `LLM_HOST` configuration
- Check model is downloaded: `ollama list`
- Test LLM endpoint: `curl http://localhost:11434/api/tags`

### High latency

- Reduce `DISCOVERY_INTERVAL`
- Increase `MAX_LOAD_THRESHOLD`
- Use a faster LLM model
- Check network bandwidth

## License

MIT

## Contributing

Contributions welcome! Please open an issue or submit a pull request.
