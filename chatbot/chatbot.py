import os
import random
import getpass
import PyPDF2
import docx
import openai
import bcrypt
import tkinter as tk
from tkinter import filedialog
import re
from collections import Counter

# Set your OpenAI API key
openai.api_key = os.getenv("OPENAI_API_KEY")

# Files to store users and remembered user
USER_FILE = "users.txt"
REMEMBER_FILE = "remember_me.txt"
USER_DATA_DIR = "user_data"
os.makedirs(USER_DATA_DIR, exist_ok=True)

responses = {
    "hi": ["Hello!", "Hey there!", "Hi! How can I help you?"],
    "how are you": ["I'm doing great! How about you?", "All good here!", "I'm fine, thanks for asking."],
    "bye": ["Goodbye!", "See you soon!", "Take care!"],
    "default": ["Sorry, I didn't understand that.", "Could you repeat?", "Hmm, I don’t know that yet."]
}

# ---------- User Handling ----------
def load_users():
    users = {}
    if os.path.exists(USER_FILE):
        with open(USER_FILE, "r") as f:
            for line in f:
                if ":" in line:
                    username, hashed = line.strip().split(":", 1)
                    users[username] = hashed.encode()
    return users

def save_user(username, password):
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
    with open(USER_FILE, "a") as f:
        f.write(f"{username}:{hashed.decode()}\n")

def save_remembered_user(username):
    with open(REMEMBER_FILE, "w") as f:
        f.write(username)

def load_remembered_user():
    if os.path.exists(REMEMBER_FILE):
        with open(REMEMBER_FILE, "r") as f:
            return f.read().strip()
    return None

def clear_remembered_user():
    if os.path.exists(REMEMBER_FILE):
        os.remove(REMEMBER_FILE)

# ---------- Chat History ----------
def get_user_chat_file(username):
    return os.path.join(USER_DATA_DIR, f"{username}_chat.txt")

def save_chat(username, user_message, bot_message):
    chat_file = get_user_chat_file(username)
    with open(chat_file, "a", encoding="utf-8") as f:
        f.write(f"You: {user_message}\n")
        f.write(f"Bot: {bot_message}\n")

# ---------- File Handling ----------
def extract_text(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    text = ""
    if not os.path.exists(file_path):
        return None, f"❌ File not found: {file_path}"
    try:
        if ext == ".pdf":
            with open(file_path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                for page in reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + " "
        elif ext == ".docx":
            doc = docx.Document(file_path)
            for para in doc.paragraphs:
                text += para.text + " "
        elif ext == ".txt":
            with open(file_path, "r", encoding="utf-8") as f:
                text = f.read()
        else:
            return None, f"❌ Unsupported file type: {ext}"
    except Exception as e:
        return None, f"❌ Error reading file: {e}"
    return text, None

# ---------- Simple Frequency-Based Summarizer ----------
STOPWORDS = set([
    "the", "and", "is", "in", "to", "of", "a", "for", "on", "with", "as",
    "by", "an", "at", "from", "or", "this", "that", "it", "be"
])

def simple_summary(text, max_sentences=5):
    # Split into sentences
    sentences = re.split(r'(?<=[.!?]) +', text)
    if len(sentences) <= max_sentences:
        return "\n".join(sentences)

    # Count word frequencies
    words = re.findall(r'\w+', text.lower())
    words = [w for w in words if w not in STOPWORDS]
    freq = Counter(words)

    # Score sentences
    sentence_scores = {}
    for s in sentences:
        s_words = re.findall(r'\w+', s.lower())
        score = sum(freq.get(w, 0) for w in s_words)
        sentence_scores[s] = score

    # Pick top sentences
    top_sentences = sorted(sentence_scores, key=sentence_scores.get, reverse=True)[:max_sentences]
    return "\n".join(top_sentences)

# ---------- Summarization ----------
def summarize_file(file_path):
    text, error = extract_text(file_path)
    if error:
        return error
    return simple_summary(text)

def summarize_multiple_files(file_paths):
    results = []
    for path in file_paths:
        path = path.strip()
        summary = summarize_file(path)
        results.append(f"📄 Summary for {os.path.basename(path)}:\n{summary}\n")
    return "\n".join(results)

# ---------- File Picker ----------
def select_files():
    root = tk.Tk()
    root.withdraw()
    file_paths = filedialog.askopenfilenames(
        title="Select files to summarize",
        filetypes=[("Text files", "*.txt"), ("PDF files", "*.pdf"), ("Word files", "*.docx")]
    )
    return list(file_paths)

# ---------- Login ----------
def login_system():
    users = load_users()
    remembered_user = load_remembered_user()
    if remembered_user:
        print(f"✅ Welcome back, {remembered_user}! You are logged in automatically.\n")
        return remembered_user
    print("🔐 Welcome! Please log in or sign up.")
    choice = input("Do you have an account? (yes/no): ").lower().strip()
    if choice == "yes":
        username = input("Username: ").strip()
        password = getpass.getpass("Password: ").strip()
        if username in users and bcrypt.checkpw(password.encode(), users[username]):
            if input("Remember me? (yes/no): ").lower().strip() == "yes":
                save_remembered_user(username)
            print(f"✅ Login successful! Welcome back, {username}.\n")
            return username
        else:
            print("❌ Invalid username or password.\n")
            return login_system()
    else:
        username = input("Choose a username: ").strip()
        while username in users:
            username = input("Username taken. Try again: ").strip()
        password = getpass.getpass("Choose a password: ").strip()
        save_user(username, password)
        if input("Remember me? (yes/no): ").lower().strip() == "yes":
            save_remembered_user(username)
        print(f"✅ Account created! Welcome, {username}.\n")
        return username

# ---------- Chatbot ----------
def chatbot(user_input, username):
    user_input_lower = user_input.lower()
    response = None
    if user_input_lower.startswith("summarize files"):
        parts = user_input.split(" ", 2)
        if len(parts) < 3 or not parts[2].strip():
            print("📂 Please select files to summarize...")
            file_paths = select_files()
            if not file_paths:
                response = "❌ No files selected."
            else:
                response = summarize_multiple_files(file_paths)
        else:
            file_paths = [p.strip() for p in parts[2].split(",")]
            response = summarize_multiple_files(file_paths)
    else:
        response = next((random.choice(responses[k]) for k in responses if k in user_input_lower), 
                        random.choice(responses["default"]))
    save_chat(username, user_input, response)
    return response

# ---------- MAIN ----------
username = login_system()
print(f"Chatbot 🤖: Hello {username}! Type 'summarize files <file1>, <file2>' or just 'summarize files' to select files.")
print("Type 'bye', 'exit', or 'logout' to quit.")

while True:
    user_message = input("You: ")
    cmd = user_message.lower().strip()
    if cmd in ["bye", "exit"]:
        print("Chatbot 🤖: Goodbye!")
        break
    elif cmd == "logout":
        clear_remembered_user()
        print("Chatbot 🤖: You have been logged out.\n")
        username = login_system()
        print(f"Chatbot 🤖: Hello {username}! Type 'summarize files <file1>, <file2>' or just 'summarize files' to select files.")
    else:
        print("Chatbot 🤖:", chatbot(user_message, username))
