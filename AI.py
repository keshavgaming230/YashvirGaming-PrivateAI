import os
import sys
import re
import threading
from pathlib import Path
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QTextBrowser, QLineEdit, QPushButton, 
                             QLabel, QComboBox, QMessageBox, QFrame, QFileDialog)
from PySide6.QtCore import Qt, Signal, QObject
from PySide6.QtGui import QFont, QDragEnterEvent, QDropEvent
from openai import OpenAI

def get_base_path():
    if getattr(sys, 'frozen', False):
        return Path(sys.argv[0]).parent
    return Path(__file__).parent

def load_local_api_key():
    base_dir = get_base_path()
    key_file_path = base_dir / "api_key.txt"
    if key_file_path.exists():
        with open(key_file_path, "r", encoding="utf-8") as f:
            key = f.read().strip()
            if key and not key.startswith("#"):
                return key
    else:
        with open(key_file_path, "w", encoding="utf-8") as f:
            f.write("API_KEY_HERE")
    return None

class WorkerSignals(QObject):
    response_received = Signal(str)
    error_received = Signal(str)
    status_changed = Signal(str, str)

class QwenWorker(threading.Thread):
    def __init__(self, text_query, api_key, model_name, signals):
        super().__init__()
        self.text_query = text_query
        self.api_key = api_key
        self.model_name = model_name
        self.signals = signals
        self.daemon = True

    def run(self):
        try:
            client = OpenAI(
                api_key=self.api_key,
                base_url="https://openrouter.ai/api/v1",
                timeout=45.0
            )

            completion = client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": self.text_query}]
            )

            answer = completion.choices[0].message.content
            self.signals.response_received.emit(answer)
            self.signals.status_changed.emit("● Agent Ready", "#00ffcc")

        except Exception as e:
            self.signals.error_received.emit(str(e))
            self.signals.status_changed.emit("● API Error", "#ff0055")

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Yashvir Gaming Private AI Agent")
        self.resize(850, 750)
        
        # Enable Drag & Drop on the window
        self.setAcceptDrops(True)
        self.attached_file_content = None
        self.attached_file_name = None

        self.cyberpunk_stylesheet = """
            QMainWindow { background-color: #0d0e15; }
            QWidget { background-color: #0d0e15; color: #00ffcc; font-family: 'Consolas', 'Segoe UI', monospace; }
            QFrame#header { background-color: #141622; border-bottom: 2px solid #ff0055; }
            QTextBrowser {
                background-color: #141622;
                border: 1px solid #00ffcc;
                border-radius: 4px;
                color: #ffffff;
                padding: 10px;
            }
            QLineEdit {
                background-color: #141622;
                border: 1px solid #ff0055;
                border-radius: 4px;
                color: #ffffff;
                padding: 8px;
            }
            QComboBox {
                background-color: #141622;
                border: 1px solid #00ffcc;
                border-radius: 4px;
                color: #00ffcc;
                padding: 5px;
                min-width: 260px;
            }
            QComboBox QAbstractItemView {
                background-color: #141622;
                selection-background-color: #ff0055;
                selection-color: #ffffff;
                border: 1px solid #00ffcc;
            }
            QPushButton {
                background-color: #1a1c2e;
                border: 2px solid #00ffcc;
                border-radius: 4px;
                color: #00ffcc;
                font-weight: bold;
                padding: 8px 15px;
            }
            QPushButton:hover { background-color: #00ffcc; color: #0d0e15; }
            QPushButton:disabled { border-color: #444444; color: #444444; }
            QPushButton#about_btn { border-color: #ff0055; color: #ff0055; }
            QPushButton#about_btn:hover { background-color: #ff0055; color: #ffffff; }
            QPushButton#file_btn { border-color: #ffcc00; color: #ffcc00; }
            QPushButton#file_btn:hover { background-color: #ffcc00; color: #0d0e15; }
        """
        self.setStyleSheet(self.cyberpunk_stylesheet)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)

        header_frame = QFrame()
        header_frame.setObjectName("header")
        header_layout = QHBoxLayout(header_frame)
        
        title_label = QLabel("⚡ YASHVIR GAMING PRIVATE AI")
        title_label.setFont(QFont("Consolas", 14, QFont.Bold))
        title_label.setStyleSheet("color: #ff0055;")
        
        self.status_label = QLabel("● Loading Config...")
        self.status_label.setFont(QFont("Consolas", 10, QFont.Bold))
        self.status_label.setStyleSheet("color: #ffcc00;")
        
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        header_layout.addWidget(self.status_label)
        main_layout.addWidget(header_frame)

        control_layout = QHBoxLayout()
        model_label = QLabel("SELECT MODEL:")
        model_label.setFont(QFont("Consolas", 9, QFont.Bold))
        
        self.model_selector = QComboBox()
        self.model_selector.addItems([
            "poolside/laguna-s-2.1:free",
            "google/gemma-4-31b-it:free",
            "cohere/north-mini-code:free",
            "openai/gpt-oss-20b:free",
            "nvidia/nemotron-3-super-120b-a12b:free"
        ])
        
        self.about_button = QPushButton("ABOUT")
        self.about_button.setObjectName("about_btn")
        self.about_button.clicked.connect(self.show_about_dialog)
        
        control_layout.addWidget(model_label)
        control_layout.addWidget(self.model_selector)
        control_layout.addStretch()
        control_layout.addWidget(self.about_button)
        main_layout.addLayout(control_layout)

        self.chat_display = QTextBrowser()
        self.chat_display.setOpenExternalLinks(True)
        self.chat_display.setFont(QFont("Consolas", 10))
        main_layout.addWidget(self.chat_display)

        # File Attachment Bar
        self.file_status_label = QLabel("")
        self.file_status_label.setFont(QFont("Consolas", 9))
        self.file_status_label.setStyleSheet("color: #ffcc00;")
        main_layout.addWidget(self.file_status_label)

        input_layout = QHBoxLayout()
        
        self.file_button = QPushButton("📁 FILE")
        self.file_button.setObjectName("file_btn")
        self.file_button.setFont(QFont("Consolas", 9, QFont.Bold))
        self.file_button.clicked.connect(self.open_file_dialog)
        
        self.user_input = QLineEdit()
        self.user_input.setPlaceholderText("Ask AI or drag & drop .txt / .py / .json files here...")
        self.user_input.setFont(QFont("Consolas", 10))
        self.user_input.returnPressed.connect(self.send_message)
        
        self.send_button = QPushButton("SEND")
        self.send_button.setFont(QFont("Consolas", 10, QFont.Bold))
        self.send_button.clicked.connect(self.send_message)
        
        input_layout.addWidget(self.file_button)
        input_layout.addWidget(self.user_input)
        input_layout.addWidget(self.send_button)
        main_layout.addLayout(input_layout)

        self.signals = WorkerSignals()
        self.signals.response_received.connect(self.handle_response)
        self.signals.error_received.connect(self.handle_error)
        self.signals.status_changed.connect(self.update_status)

        self.api_key = load_local_api_key()
        if not self.api_key or self.api_key == "API_KEY_HERE":
            self.update_status("● Config Missing", "#ff0055")
            self.send_button.setEnabled(False)
            self.append_to_chat("System", "Error: 'API KEY' missing in api_key.txt.")
        else:
            self.update_status("● Agent Ready", "#00ffcc")
            self.append_to_chat("Agent", "System initialized. You can now drag and drop text/code files directly into the window.")

    # Drag & Drop Handlers
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            if file_path:
                self.process_file(file_path)
                break

    def open_file_dialog(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select File", "", "Text & Code Files (*.txt *.py *.json *.js *.html *.css *.md);;All Files (*)"
        )
        if file_path:
            self.process_file(file_path)

    def process_file(self, file_path):
        try:
            path = Path(file_path)
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            self.attached_file_content = content
            self.attached_file_name = path.name
            self.file_status_label.setText(f"📎 Attached: {path.name} ({len(content)} chars)")
            self.append_to_chat("System", f"File attached successfully: {path.name}")
        except Exception as e:
            self.append_to_chat("System", f"Failed to read file: {str(e)}")

    def update_status(self, text, color):
        self.status_label.setText(text)
        self.status_label.setStyleSheet(f"color: {color};")

    def format_code_blocks(self, text):
        def replace_code_block(match):
            lang = match.group(1).strip() if match.group(1) else "code"
            code_content = match.group(2).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            return f"""
            <div style="background-color: #090a0f; border: 1px solid #ff0055; border-radius: 6px; margin: 8px 0px;">
                <div style="background-color: #141622; padding: 4px 10px; border-bottom: 1px solid #333344; color: #ff0055; font-weight: bold; font-size: 11px;">
                    {lang.upper()}
                </div>
                <pre style="padding: 10px; color: #00ffcc; font-family: 'Consolas', monospace; white-space: pre-wrap; word-wrap: break-word; margin: 0;">{code_content}</pre>
            </div>
            """
        formatted_text = re.sub(r'```(\w+)?\n(.*?)```', replace_code_block, text, flags=re.DOTALL)
        formatted_text = formatted_text.replace('\n', '<br>')
        return formatted_text

    def append_to_chat(self, sender, message):
        if sender == "User":
            html_msg = f"<b style='color:#ff0055;'>👤 YOU:</b><br><span style='color:#ffffff;'>{message}</span><br><br>"
        elif sender == "Agent":
            parsed_content = self.format_code_blocks(message)
            html_msg = f"<b style='color:#00ffcc;'>🤖 AGENT:</b><br><span style='color:#ffffff;'>{parsed_content}</span><br><br>"
        elif sender == "System":
            html_msg = f"<b style='color:#ffcc00;'>⚙️ SYSTEM NOTICE: {message}</b><br><br>"

        self.chat_display.append(html_msg)

    def send_message(self):
        query = self.user_input.text().strip()
        
        if not query and not self.attached_file_content:
            return

        full_prompt = query
        if self.attached_file_content:
            full_prompt = f"File Context [{self.attached_file_name}]:\n```\n{self.attached_file_content}\n```\n\nUser Question: {query}"
            self.attached_file_content = None
            self.attached_file_name = None
            self.file_status_label.setText("")

        self.append_to_chat("User", query if query else f"[Sent Attached File]")
        self.user_input.clear()
        self.update_status("● AI is thinking...", "#ffcc00")
        
        selected_model = self.model_selector.currentText()
        worker = QwenWorker(full_prompt, self.api_key, selected_model, self.signals)
        worker.start()

    def handle_response(self, text):
        self.append_to_chat("Agent", text)
        self.update_status("● Agent Ready", "#00ffcc")
    
    def handle_error(self, text):
        self.append_to_chat("System", f"Execution failed: {text}")
        self.update_status("● Agent Ready", "#00ffcc")
        
    def show_about_dialog(self):
        about_box = QMessageBox(self)
        about_box.setWindowTitle("System Manifest")
        about_box.setStyleSheet(
            "QMessageBox {background-color: #141622;border: 2px solid #ff0055;}"
            "QLabel {color: #ffffff;font-family: 'Consolas';}"
            "QPushButton {background-color: #1a1c2e;border: 1px solid #00ffcc;color: #00ffcc;padding: 5px 15px;}"
            "QPushButton:hover {background-color: #00ffcc;color: #0d0e15;}"
        )
        manifest_text = (
            "========================================\n"
            " APPLICATION METRICS\n"
            "========================================\n"
            "Tool Version: 1.0.4 (FILE UPLOAD EDITION)\n"
            "Architecture: Python AI Agent\n"
            "Coded by    : Yashvir Gaming\n"
        )
        about_box.setText(manifest_text)
        about_box.exec()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())