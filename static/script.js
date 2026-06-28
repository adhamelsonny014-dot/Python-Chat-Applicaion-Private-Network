// DOM Elements
const messageInput = document.getElementById('message-input');
const sendButton = document.getElementById('send-button');
const messagesContainer = document.getElementById('messages');
const otherUserName = document.getElementById('other-user-name');
const otherUserAvatar = document.getElementById('other-user-avatar');
const userStatus = document.getElementById('user-status');

// Initialize Socket.io
const socket = io();
let currentUser = {};
let otherUser = {};

// Initialize the chat
document.addEventListener('DOMContentLoaded', () => {
    fetch('/get-user-data')
        .then(response => response.json())
        .then(data => {
            currentUser = data.user;
            otherUser = data.otherUser;
            updateUI();
            
            if (data.isServer) {
                userStatus.textContent = 'Waiting for connection...';
                userStatus.className = 'offline';
            }
        })
        .catch(error => {
            console.error('Error fetching user data:', error);
        });

    // Socket event handlers
    socket.on('connect', () => {
        console.log('Connected to WebSocket server');
    });

    socket.on('message', (msg) => {
        if (msg.text.toLowerCase() === 'deactivatechat1234') {
            addSystemMessage('Chat deactivated');
            return;
        }
        addMessage(msg.text, 'received', msg.sender, new Date(msg.timestamp));
    });

    socket.on('user-connected', (user) => {
        otherUser.online = true;
        updateUI();
        addSystemMessage(`${user.name} connected`);
    });

    socket.on('user-disconnected', (user) => {
        otherUser.online = false;
        updateUI();
        addSystemMessage(`${user.name} disconnected`);
    });

    socket.on('status-update', (status) => {
        userStatus.textContent = status.text;
        userStatus.className = status.class;
    });

    socket.on('error', (error) => {
        addSystemMessage(`Error: ${error.message}`);
    });
});

function updateUI() {
    otherUserName.textContent = otherUser.name;
    otherUserAvatar.src = otherUser.avatar;
    userStatus.textContent = otherUser.online ? 'Online' : 'Offline';
    userStatus.className = otherUser.online ? 'online' : 'offline';
}

function addSystemMessage(text) {
    const div = document.createElement('div');
    div.className = 'system-message';
    div.innerHTML = `<span>${text}</span>`;
    messagesContainer.appendChild(div);
    scrollToBottom();
}

function sendMessage() {
    const messageText = messageInput.value.trim();
    if (!messageText) return;

    const timestamp = new Date();
    
    if (messageText.toLowerCase() === 'deactivatechat1234') {
        socket.emit('deactivate');
        addSystemMessage('Chat deactivated');
        messageInput.value = '';
        return;
    }

    const msg = {
        text: messageText,
        sender: currentUser,
        timestamp: timestamp.toISOString()
    };

    addMessage(messageText, 'sent', currentUser, timestamp);
    socket.emit('message', msg);
    messageInput.value = '';
}

function addMessage(text, type, sender, timestamp) {
    const div = document.createElement('div');
    div.className = `message ${type}`;
    
    const timeString = formatTime(timestamp);
    const senderName = type === 'received' ? `<div class="message-sender">${sender.name}</div>` : '';
    
    div.innerHTML = `
        ${senderName}
        <div class="message-text">${text}</div>
        <div class="message-meta">
            <span class="message-time">${timeString}</span>
        </div>
    `;
    
    messagesContainer.appendChild(div);
    scrollToBottom();
}

function formatTime(date) {
    let hours = date.getHours();
    const minutes = date.getMinutes().toString().padStart(2, '0');
    const ampm = hours >= 12 ? 'PM' : 'AM';
    hours = hours % 12 || 12;
    return `${hours}:${minutes} ${ampm}`;
}

function scrollToBottom() {
    setTimeout(() => {
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }, 50);
}

// Event listeners
sendButton.addEventListener('click', sendMessage);
messageInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') sendMessage();
});