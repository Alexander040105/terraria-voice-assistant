import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget, QTextEdit, QLabel
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from langchain_ollama.llms import OllamaLLM
from langchain_core.prompts import ChatPromptTemplate
from vector import retriever
import speech_recognition as sr
import pyttsx3
import time
import os


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
engine.setProperty('voice', voices[0].id)
curr_dir = os.getcwd()
def speak_ai(text):
    engine.say(text)
    engine.runAndWait()

def voice_input():
    recognizer = sr.Recognizer()
    mic = sr.Microphone()
    speak_ai("Ask me a question about Terraria!")
    ai_label.setText("Ask me a q uestion about Terraria!")
    
    with mic as source:
        print("\n🎤 Listening... (say 'q' to quit)")
        recognizer.adjust_for_ambient_noise(source, duration=0.5)
        audio = recognizer.listen(source, timeout=15, phrase_time_limit=30)
        try:
            question = recognizer.recognize_google(audio)
        except sr.WaitTimeoutError:
            ai_label.setText("⏱️ No speech detected")
            return
        except sr.UnknownValueError:
            ai_label.setText("🤷 Couldn't understand audio")
            return
        except Exception as e:
            ai_label.setText(f"❌ Error: {e}")
            return
    docs = retriever.invoke(question)
    wiki = "\n\n".join(doc.page_content for doc in docs)

    answer = chain.invoke({"wiki": wiki, "question": question})
    speak_ai(answer)
    ai_label.setText("")
    ai_label.setText(f"Q: {question}\n A: {answer}")
    time.sleep(5)
    ai_label.setText("")
    
with open(f'{curr_dir}\\style.qss', 'r') as f:
    style = f.read()
    

    
app = QApplication(sys.argv)
window = QMainWindow()
window.setWindowFlags(Qt.WindowStaysOnTopHint)
window.setObjectName('mainWindow')
window.setWindowTitle("Terraria Wiki Voice Assistant")
window.resize(200,100)
qr = window.frameGeometry()
top_right = app.primaryScreen().availableGeometry().topRight()
qr.moveTopRight(top_right)
window.move(qr.topLeft()- window.rect().topRight())
# window.setWindowIcon(None)

app.setStyleSheet(style)
container = QWidget()
window.setCentralWidget(container)

header = QLabel("Terraria Wiki Voice Assistant", parent=container)
header.setAlignment(Qt.AlignCenter)
header.setFont(QFont("Poppins", 20, QFont.Bold))
header.setObjectName("header")

voice_button = QPushButton("Start Voice Input", parent=container)
voice_button.setCheckable(True)
voice_button.clicked.connect(voice_input)
voice_button.setObjectName("voiceButton")

ai_label = QLabel(parent=container)
ai_label.setFont(QFont("Poppins", 10))
ai_label.setAlignment(Qt.AlignCenter)
ai_label.setObjectName("aiLabel")
layout = QVBoxLayout(container)

#adding the widgets to the layout
layout.addWidget(header)
layout.addWidget(voice_button)
layout.addWidget(ai_label)
window.show()
app.exec()

