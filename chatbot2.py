import os
import random
import getpass
import PyPDF2
import docx
import bcrypt
import tkinter as tk
from tkinter import filedialog, scrolledtext
import re
from collections import Counter
import pytesseract
from PIL import Image
from pdf2image import convert_from_path

# ------------------- CONFIG -------------------
# If Tesseract is not in PATH, set it manually (Windows example):
# pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

USER_FILE = "users.txt"
REMEMBER_FILE = "remember_me.txt"
USER_DATA_DIR = "user_data"
os.makedirs(USER_DATA_DIR, exist_ok=True)

STOPWORDS = set([
    "the", "and", "is", "in", "to", "of", "a", "for", "on", "with", "as",
    "by", "an", "at", "from", "or", "this", "that", "it", "be"
])

responses = {
    "hi": ["Hello!", "Hey there!", "Hi! How can I help you?"],
    "how are you": ["I'm doing great! How about you?", "All good here!", "I'm fine, thanks for asking."],
    "bye": ["Goodbye!", "See you soon!", "Take care!"],
    "default": ["Sorry, I didn't understand that.", "Could you repeat?", "Hmm, I don’t know that yet."]
}

# ------------------- USER HANDLING -------------------
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

# ------------------- CHAT HISTORY -------------------
def get_user_chat_file(username):
    return os.path.join(USER_DATA_DIR, f"{username}_chat.txt")

def save_chat(username, user_message, bot_message):
    chat_file = get_user_chat_file(username)
    with open(chat_file, "a", encoding="utf-8") as f:
        f.write(f"You: {user_message}\n")
        f.write(f"Bot: {bot_message}\n")

# ------------------- FILE EXTRACTION & SUMMARIZATION -------------------
def extract_text_from_file(file_path):
    text = ""
    ocr_used = False

    try:
        if file_path.endswith(".pdf"):
            # Extract text normally
            with open(file_path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                for page in reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"

            # Fallback to OCR if no text
            if not text.strip():
                ocr_used = True
                images = convert_from_path(file_path)
                for img in images:
                    text += pytesseract.image_to_string(img) + "\n"

        elif file_path.endswith(".docx"):
            doc = docx.Document(file_path)
            for para in doc.paragraphs:
                text += para.text + "\n"

        elif file_path.endswith(".txt"):
            with open(file_path, "r", encoding="utf-8") as f:
                text = f.read()

        else:
            return "❌ Unsupported file format.", ocr_used

    except Exception as e:
        return f"❌ Error reading file: {e}", ocr_used

    return text.strip(), ocr_used

def simple_summary(text, max_sentences=5):
    sentences = re.split(r'(?<=[.!?]) +', text)
    if len(sentences) <= max_sentences:
        return "\n".join(sentences)

    words = re.findall(r'\w+', text.lower())
    words = [w for w in words if w not in STOPWORDS]
    freq = Counter(words)

    sentence_scores = {}
    for s in sentences:
        s_words = re.findall(r'\w+', s.lower())
        score = sum(freq.get(w, 0) for w in s_words)
        sentence_scores[s] = score

    top_sentences = sorted(sentence_scores, key=sentence_scores.get, reverse=True)[:max_sentences]
    return "\n".join(top_sentences)

def summarize_file(file_path):
    text, ocr_used = extract_text_from_file(file_path)
    if not text or text.startswith("❌"):
        return text

    summary = simple_summary(text)
    if ocr_used:
        return f"📑 (OCR Used)\n{summary}"
    return summary

# ------------------- GUI CHATBOT -------------------
class ChatbotGUI:
    def __init__(self, root, username):
        self.root = root
        self.root.title("Chatbot 🤖")
        self.username = username

        self.chat_area = scrolledtext.ScrolledText(root, wrap=tk.WORD, width=70, height=20, state="disabled")
        self.chat_area.pack(padx=10, pady=10)

        self.entry = tk.Entry(root, width=70)
        self.entry.pack(side=tk.LEFT, padx=10, pady=10, expand=True, fill=tk.X)
        self.entry.bind("<Return>", self.send_message)

        self.send_button = tk.Button(root, text="Send", command=self.send_message)
        self.send_button.pack(side=tk.RIGHT, padx=10, pady=10)

        self.display_message("Chatbot 🤖", f"Hello {username}! Type 'summarize files' to upload and summarize documents.\nType 'bye', 'exit', or 'logout' to quit.")

    def display_message(self, sender, message):
        self.chat_area.config(state="normal")
        self.chat_area.insert(tk.END, f"{sender}: {message}\n")
        self.chat_area.yview(tk.END)
        self.chat_area.config(state="disabled")

    def send_message(self, event=None):
        user_message = self.entry.get().strip()
        if not user_message:
            return

        self.display_message(self.username, user_message)
        self.entry.delete(0, tk.END)

        cmd = user_message.lower().strip()
        if cmd in ["bye", "exit"]:
            self.display_message("Chatbot 🤖", "Goodbye!")
            self.root.quit()
        elif cmd == "logout":
            clear_remembered_user()
            self.display_message("Chatbot 🤖", "You have been logged out. Restart the app to log in again.")
            self.root.quit()
        elif cmd.startswith("summarize files"):
            file_paths = filedialog.askopenfilenames(
                title="Select files to summarize",
                filetypes=[("Documents", "*.pdf *.docx *.txt")]
            )
            if not file_paths:
                bot_response = "❌ No files selected."
            else:
                summaries = []
                for path in file_paths:
                    self.display_message("📂", f"Processing file: {os.path.basename(path)}")
                    summary = summarize_file(path)
                    summaries.append(f"📄 Summary for {os.path.basename(path)}:\n{summary}")
                bot_response = "\n\n".join(summaries)
        else:
            bot_response = next((random.choice(responses[k]) for k in responses if k in cmd),
                                random.choice(responses["default"]))

        self.display_message("Chatbot 🤖", bot_response)
        save_chat(self.username, user_message, bot_response)

# ------------------- LOGIN SYSTEM -------------------
def login_system():
    users = load_users()
    remembered_user = load_remembered_user()
    if remembered_user:
        return remembered_user

    choice = input("Do you have an account? (yes/no): ").lower().strip()
    if choice == "yes":
        username = input("Username: ").strip()
        password = getpass.getpass("Password: ").strip()
        if username in users and bcrypt.checkpw(password.encode(), users[username]):
            if input("Remember me? (yes/no): ").lower().strip() == "yes":
                save_remembered_user(username)
            return username
        else:
            print("❌ Invalid username or password.")
            return login_system()
    else:
        username = input("Choose a username: ").strip()
        while username in users:
            username = input("Username taken. Try again: ").strip()
        password = getpass.getpass("Choose a password: ").strip()
        save_user(username, password)
        if input("Remember me? (yes/no): ").lower().strip() == "yes":
            save_remembered_user(username)
        return username

# ------------------- MAIN -------------------
if __name__ == "__main__":
    username = login_system()
    root = tk.Tk()
    gui = ChatbotGUI(root, username)
    root.mainloop()
