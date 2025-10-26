const API_BASE = '';
let updateInterval;

function formatUptime(seconds) {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);
    return `${hours}h ${minutes}m ${secs}s`;
}

function formatTimestamp(timestamp) {
    const date = new Date(timestamp);
    return date.toLocaleString();
}

function getStatusClass(status) {
    const statusMap = {
        'pending': 'status-pending',
        'assigned': 'status-assigned',
        'running': 'status-running',
        'completed': 'status-completed',
        'failed': 'status-failed'
    };
    return statusMap[status] || 'status-pending';
}

async function fetchHealth() {
    try {
        const response = await fetch(`${API_BASE}/health`);
        const data = await response.json();

        document.getElementById('node-id').textContent = data.node_id.substring(0, 8);
        document.getElementById('node-name').textContent = data.node_name;
        document.getElementById('uptime').textContent = formatUptime(data.uptime);
        document.getElementById('cpu').textContent = `${data.cpu_percent.toFixed(1)}%`;
        document.getElementById('memory').textContent = `${data.memory_percent.toFixed(1)}%`;
        document.getElementById('load').textContent = `${(data.load * 100).toFixed(1)}%`;
        document.getElementById('qos').textContent = `${(data.qos * 100).toFixed(1)}%`;
        document.getElementById('active-tasks').textContent = data.active_tasks;

        updateRoles(data.active_roles);

    } catch (error) {
        console.error('Error fetching health:', error);
    }
}

async function fetchPeers() {
    try {
        const response = await fetch(`${API_BASE}/peers`);
        const peers = await response.json();

        const peerCount = document.getElementById('peers-count');
        const peersList = document.getElementById('peers-list');

        peerCount.textContent = `${peers.length} peer${peers.length !== 1 ? 's' : ''}`;

        if (peers.length === 0) {
            peersList.innerHTML = '<p class="empty-message">No peers discovered</p>';
        } else {
            peersList.innerHTML = peers.map(peer => `
                <div class="peer-item">
                    <div class="peer-header">
                        <span class="peer-id">${peer.peer_id.substring(0, 8)}</span>
                        <span class="peer-ip">${peer.ip}:${peer.port}</span>
                    </div>
                    <div class="peer-details">
                        <span class="peer-stat">Load: ${(peer.load * 100).toFixed(1)}%</span>
                        <span class="peer-stat">QoS: ${(peer.qos * 100).toFixed(1)}%</span>
                        <span class="peer-stat">Roles: ${peer.roles.join(', ') || 'None'}</span>
                    </div>
                </div>
            `).join('');
        }

    } catch (error) {
        console.error('Error fetching peers:', error);
    }
}

async function fetchTasks() {
    try {
        const response = await fetch(`${API_BASE}/tasks`);
        const tasks = await response.json();

        const tasksContainer = document.getElementById('tasks-container');

        if (tasks.length === 0) {
            tasksContainer.innerHTML = '<p class="empty-message">No tasks yet</p>';
        } else {
            const recentTasks = tasks.slice(-10).reverse();
            tasksContainer.innerHTML = recentTasks.map(task => `
                <div class="task-item ${getStatusClass(task.status)}">
                    <div class="task-header">
                        <span class="task-id">${task.task_id.substring(0, 8)}</span>
                        <span class="task-status">${task.status}</span>
                    </div>
                    <div class="task-body">
                        <div class="task-role">${task.role}</div>
                        <div class="task-prompt">${task.prompt.substring(0, 100)}${task.prompt.length > 100 ? '...' : ''}</div>
                        ${task.result ? `<div class="task-result">${task.result.substring(0, 200)}${task.result.length > 200 ? '...' : ''}</div>` : ''}
                        ${task.error ? `<div class="task-error">${task.error}</div>` : ''}
                    </div>
                    <div class="task-footer">
                        <span class="task-time">${formatTimestamp(task.created_at)}</span>
                        ${task.assigned_peer ? `<span class="task-peer">Peer: ${task.assigned_peer.substring(0, 8)}</span>` : ''}
                    </div>
                </div>
            `).join('');
        }

    } catch (error) {
        console.error('Error fetching tasks:', error);
    }
}

function updateRoles(roles) {
    const rolesList = document.getElementById('roles-list');

    if (!roles || roles.length === 0) {
        rolesList.innerHTML = '<p class="empty-message">No active roles</p>';
    } else {
        rolesList.innerHTML = roles.map(role => `
            <div class="role-badge">${role}</div>
        `).join('');
    }
}

async function submitTask(event) {
    event.preventDefault();

    const role = document.getElementById('task-role').value;
    const prompt = document.getElementById('task-prompt').value;

    try {
        const response = await fetch(`${API_BASE}/tasks`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                role: role,
                prompt: prompt,
                priority: 1
            })
        });

        const result = await response.json();

        if (response.ok) {
            alert(`Task submitted successfully! Task ID: ${result.task_id}`);
            document.getElementById('task-prompt').value = '';
            await fetchTasks();
        } else {
            alert(`Failed to submit task: ${result.detail || 'Unknown error'}`);
        }

    } catch (error) {
        console.error('Error submitting task:', error);
        alert(`Error submitting task: ${error.message}`);
    }
}

async function updateDashboard() {
    await Promise.all([
        fetchHealth(),
        fetchPeers(),
        fetchTasks()
    ]);

    document.getElementById('last-update').textContent = new Date().toLocaleTimeString();
}

function setupTabs() {
    const tabButtons = document.querySelectorAll('.tab-button');
    const tabContents = document.querySelectorAll('.tab-content');

    tabButtons.forEach(button => {
        button.addEventListener('click', () => {
            const tabName = button.getAttribute('data-tab');

            tabButtons.forEach(btn => btn.classList.remove('active'));
            tabContents.forEach(content => content.classList.remove('active'));

            button.classList.add('active');
            document.getElementById(`${tabName}-tab`).classList.add('active');
        });
    });
}

document.addEventListener('DOMContentLoaded', () => {
    const taskForm = document.getElementById('task-form');
    taskForm.addEventListener('submit', submitTask);

    setupTabs();
    updateDashboard();

    updateInterval = setInterval(updateDashboard, 3000);
});

window.addEventListener('beforeunload', () => {
    if (updateInterval) {
        clearInterval(updateInterval);
    }
});
