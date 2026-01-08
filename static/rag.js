console.log("Maternal Health AI Chat Loaded");

let chats = [];
let currentChatId = null;

/* =========================
   ON LOAD
========================= */
window.onload = async function () {
    await loadChatList();
};

/* =========================
   LOAD CHAT LIST
========================= */
async function loadChatList() {
    const res = await fetch("http://127.0.0.1:8000/chats");
    chats = await res.json();

    renderChatList();

    if (chats.length > 0) {
        await loadChat(chats[0].chat_id);
    }
}

/* =========================
   RENDER SIDEBAR
========================= */
function renderChatList() {
    const chatList = document.getElementById("chatList");
    chatList.innerHTML = "";

    chats.forEach(chat => {
        const div = document.createElement("div");
        div.className = "chat-item" + (chat.chat_id === currentChatId ? " active" : "");
        div.onclick = () => loadChat(chat.chat_id);

        div.innerHTML = `
            <span>${chat.title}</span>
            <div class="chat-actions">
                <button onclick="event.stopPropagation(); renameChat('${chat.chat_id}')">✏️</button>
                <button onclick="event.stopPropagation(); deleteChat('${chat.chat_id}')">🗑️</button>
            </div>
        `;

        chatList.appendChild(div);
    });
}

/* =========================
   LOAD CHAT
========================= */
async function loadChat(chatId) {
    currentChatId = chatId;

    const res = await fetch(`http://127.0.0.1:8000/chat/${chatId}`);
    const chat = await res.json();

    document.getElementById("chatTitle").value = chat.title;

    const chatbox = document.getElementById("chatbox");
    chatbox.innerHTML = "";

    chat.messages.forEach(msg => addMessage(msg.role, msg.text));

    renderChatList();
}

/* =========================
   RENAME CHAT
========================= */
async function renameChat(chatId) {
    const newName = prompt("Enter new chat title:");
    if (!newName) return;

    await fetch(`http://127.0.0.1:8000/chat/${chatId}/title`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: newName })
    });

    await loadChatList();
}

/* Save title button */
document.getElementById("saveTitleBtn").onclick = async () => {
    if (!currentChatId) return;

    const newName = document.getElementById("chatTitle").value;

    await fetch(`http://127.0.0.1:8000/chat/${currentChatId}/title`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: newName })
    });

    await loadChatList();
};

/* =========================
   DELETE CHAT
========================= */
async function deleteChat(chatId) {
    if (!confirm("Delete this chat?")) return;

    await fetch(`http://127.0.0.1:8000/chat/${chatId}`, { method: "DELETE" });
    await loadChatList();
}

/* =========================
   NEW CHAT
========================= */
document.getElementById("newChatBtn").onclick = async () => {
    const res = await fetch("http://127.0.0.1:8000/chat/new", { method: "POST" });
    const chat = await res.json();

    await loadChatList();
    await loadChat(chat.chat_id);
};

/* =========================
   SEND MESSAGE
========================= */
document.getElementById("sendBtn").onclick = sendMessage;
document.getElementById("query").addEventListener("keypress", e => {
    if (e.key === "Enter") sendMessage();
});

async function sendMessage() {
    if (!currentChatId) {
        alert("Please create or select a chat first.");
        return;
    }

    const query = document.getElementById("query").value.trim();
    if (!query) return;

    addMessage("user", query);
    const loading = addMessage("assistant", "Typing...");

    try {
        const res = await fetch(`http://127.0.0.1:8000/chat/${currentChatId}/send`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ query })
        });

        const data = await res.json();
        loading.innerHTML = `<strong>Bot:</strong> ${data.bot || "No response."}`;

    } catch (err) {
        loading.innerHTML = `<strong>Bot:</strong> Server error.`;
    }

    document.getElementById("query").value = "";
}

/* =========================
   ADD MESSAGE TO UI
========================= */
function addMessage(role, message) {
    const chatbox = document.getElementById("chatbox");
    const div = document.createElement("div");

    div.className = `msg ${role}`;
    div.innerHTML = `<strong>${role === "user" ? "You" : "Bot"}:</strong> ${message}`;

    chatbox.appendChild(div);
    chatbox.scrollTop = chatbox.scrollHeight;

    return div;
}
