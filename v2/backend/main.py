from flask import Flask, render_template, request
from flask_cors import CORS
from langchain_ollama.llms import OllamaLLM
from langchain_core.prompts import ChatPromptTemplate
from vector import retriever
import speech_recognition as sr
import pyttsx3
import os
import jsonify
app = Flask(__name__)
CORS(app)

recognizer = sr.Recognizer()
mic = sr.Microphone()
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

def speak_ai(text):
    engine = pyttsx3.init()
    voices = engine.getProperty('voices')
    engine.setProperty('voice', voices[1].id)
    engine.say(text)
    engine.runAndWait()


@app.route("/api/talk", methods=["POST", "GET"])
def talk():
    question = request.json.get("message", "")
    docs = retriever.invoke(question)
    wiki = "\n\n".join(doc.page_content for doc in docs)
    answer = chain.invoke({"wiki": wiki, "question": question})
    # while True:
    #     with mic as source:
    #         speak_ai("Ask me a question about Terraria!")
    #         recognizer.adjust_for_ambient_noise(source, duration=0.5)
    #         audio = recognizer.listen(source, timeout=15, phrase_time_limit=30)
    #     try:
    #         question = recognizer.recognize_google(audio)
    #     except:
    #         continue

    #     if question.lower() == "q":
    #         break

    #     print(f"\n🗣️ You asked: {question}")

    #     docs = retriever.invoke(question)
    #     wiki = "\n\n".join(doc.page_content for doc in docs)

    #     answer = chain.invoke({"wiki": wiki, "question": question})
    #     speak_ai(answer)
    #     print("\n🤖", answer)
    
    data = {"question": question, "answer": answer}
    
    return jsonify(data)

@app.route("/")
def home():
    return "Test"

if __name__ == "__main__":
    app.run(debug=True, port=5000) 
    