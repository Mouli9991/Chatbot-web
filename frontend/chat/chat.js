// Get token from localStorage
const token = localStorage.getItem('access_token');

if (!token) {
    window.location.href = '/login';
}

// DOM elements
const messagesContainer = document.getElementById('messages');
const chatForm = document.getElementById('chatForm');
const messageInput = document.getElementById('messageInput');
const fileUpload = document.getElementById('fileUpload');

// Function to add a message to the chat
function addMessage(text, isUser) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${isUser ? 'user-message' : 'bot-message'}`;
    
    const messageP = document.createElement('p');
    messageP.textContent = text;
    
    messageDiv.appendChild(messageP);
    messagesContainer.appendChild(messageDiv);
    
    // Scroll to bottom
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

// Function to handle sending a message
async function sendMessage(message) {
    // Add user message to chat
    addMessage(message, true);
    
    try {
        const formData = new FormData();
        formData.append('message', message);
        
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`
            },
            body: formData
        });
        
        if (response.ok) {
            const data = await response.json();
            addMessage(data.response, false);
        } else {
            const errorData = await response.json();
            addMessage(`Error: ${errorData.detail || 'Failed to get response'}`, false);
        }
    } catch (error) {
        console.error('Chat error:', error);
        addMessage('An error occurred while sending your message', false);
    }
}

// Handle chat form submission
chatForm.addEventListener('submit', function(e) {
    e.preventDefault();
    
    const message = messageInput.value.trim();
    if (message) {
        sendMessage(message);
        messageInput.value = '';
    }
});

// Handle file uploads
fileUpload.addEventListener('change', async function(e) {
    const files = e.target.files;
    
    if (files.length === 0) return;
    
    // Add message indicating file upload
    addMessage(`Uploading ${files.length} file(s)...`, true);
    
    for (let i = 0; i < files.length; i++) {
        const file = files[i];
        
        const formData = new FormData();
        formData.append('file', file);
        
        try {
            const response = await fetch('/api/upload', {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`
                },
                body: formData
            });
            
            if (response.ok) {
                const data = await response.json();
                addMessage(`Successfully uploaded: ${data.filename}`, false);
            } else {
                const errorData = await response.json();
                addMessage(`Error uploading ${file.name}: ${errorData.detail || 'Upload failed'}`, false);
            }
        } catch (error) {
            console.error('Upload error:', error);
            addMessage(`Error uploading ${file.name}: ${error.message}`, false);
        }
    }
    
    // Reset file input
    fileUpload.value = '';
});

// Initial bot message
addMessage("Hello! I'm your banking assistant. How can I help you today?", false);