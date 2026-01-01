import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget, QTextEdit, QLabel, QFrame, QGraphicsDropShadowEffect
from PyQt5.QtCore import Qt, QPropertyAnimation, QEasingCurve, QRect, pyqtProperty
from PyQt5.QtGui import QFont, QColor, QPalette, QIcon
from langchain_ollama.llms import OllamaLLM
from langchain_core.prompts import ChatPromptTemplate
from vector import retriever
import speech_recognition as sr
import pyttsx3
import time


model = OllamaLLM(model="llama3.2")

template = """
You are a Terraria Wiki expert.
Always answer using in-game mechanics only and explain it in a Dr.House way.
If the information is not in the wiki context, say that you don't know and do not make up an answer.

Wiki context:
{wiki}

Question:
{question}
"""

prompt = ChatPromptTemplate.from_template(template)
chain = prompt | model
engine = pyttsx3.init()
voices = engine.getProperty('voices')
engine.setProperty('voice', voices[1].id)

def speak_ai(text):
    engine.say(text)
    engine.runAndWait()

class ModernButton(QPushButton):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setFixedSize(240, 60)
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet("""
            QPushButton {
                background-color: #1e1e2e;
                color: #cdd6f4;
                border: 2px solid #89b4fa;
                border-radius: 30px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #89b4fa;
                color: #1e1e2e;
            }
            QPushButton:pressed {
                background-color: #74c7ec;
            }
        """)

class ChatBubble(QFrame):
    def __init__(self, text, is_ai=True, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.label = QLabel(text)
        self.label.setWordWrap(True)
        self.label.setFont(QFont("Segoe UI", 11))
        
        if is_ai:
            self.setStyleSheet("background-color: #313244; border-radius: 15px; color: #cdd6f4; margin-right: 40px;")
            self.label.setStyleSheet("padding: 10px;")
        else:
            self.setStyleSheet("background-color: #89b4fa; border-radius: 15px; color: #1e1e2e; margin-left: 40px;")
            self.label.setStyleSheet("padding: 10px; font-weight: bold;")
            
        self.layout.addWidget(self.label)

class TerrariaAssistant(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Dr. House - Terraria Protocol")
        self.setFixedSize(500, 700)
        self.setStyleSheet("background-color: #11111b;")

        self.container = QWidget()
        self.setCentralWidget(self.container)
        self.layout = QVBoxLayout(self.container)
        self.layout.setContentsMargins(30, 40, 30, 40)
        self.layout.setSpacing(20)

        # Header
        self.header = QLabel("WIKI DIAGNOSIS")
        self.header.setAlignment(Qt.AlignCenter)
        self.header.setStyleSheet("color: #89b4fa; font-size: 24px; font-weight: bold; letter-spacing: 2px;")
        self.layout.addWidget(self.header)

        # Subheader
        self.subheader = QLabel("Dr. House's Assistant")
        self.subheader.setAlignment(Qt.AlignCenter)
        self.subheader.setStyleSheet("color: #6c7086; font-size: 14px;")
        self.layout.addWidget(self.subheader)

        # Chat Area
        self.scroll_area = QWidget()
        self.chat_layout = QVBoxLayout(self.scroll_area)
        self.chat_layout.setAlignment(Qt.AlignTop)
        self.layout.addWidget(self.scroll_area, 1)

        # Button
        self.voice_button = ModernButton("INITIALIZE PROTOCOL")
        self.voice_button.clicked.connect(self.start_voice)
        self.layout.addWidget(self.voice_button, 0, Qt.AlignCenter)

        # Status
        self.status_label = QLabel("SYSTEM IDLE")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("color: #fab387; font-size: 12px; font-weight: bold;")
        self.layout.addWidget(self.status_label)

    def add_message(self, text, is_ai=True):
        bubble = ChatBubble(text, is_ai)
        self.chat_layout.addWidget(bubble)
        # In a real app, you'd scroll to bottom here

    def start_voice(self):
        self.status_label.setText("LISTENING...")
        self.status_label.setStyleSheet("color: #a6e3a1;")
        recognizer = sr.Recognizer()
        mic = sr.Microphone()
        with mic as source:
            print("\n🎤 Listening... (say 'q' to quit)")
            recognizer.adjust_for_ambient_noise(source, duration=0.5)
            audio = recognizer.listen(source, timeout=15, phrase_time_limit=30)
        try:
            question = recognizer.recognize_google(audio)
        except sr.WaitTimeoutError:
            self.status_label.setText("⏱️ No speech detected")
            return
        except sr.UnknownValueError:
            self.status_label.setText("🤷 Couldn't understand audio")
            return
        except Exception as e:
            self.status_label.setText(f"❌ Error: {e}")
            return
        docs = retriever.invoke(question)
        wiki = "\n\n".join(doc.page_content for doc in docs)

        answer = chain.invoke({"wiki": wiki, "question": question})
        speak_ai(answer)
        self.add_message(question, is_ai=False)
        self.add_message(answer)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TerrariaAssistant()
    window.show()
    sys.exit(app.exec_())
