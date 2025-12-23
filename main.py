from langchain_ollama.llms import OllamaLLM
from langchain_core.prompts import ChatPromptTemplate
from vector import retriever
import speech_recognition as sr
import pyttsx3

recognizer = sr.Recognizer()
mic = sr.Microphone()
    
model = OllamaLLM(model="llama3.2")

template = """
You are an expert in answering questions about a terraria game wiki

Here are some relevant wiki entries: {wiki}

Here is the question to answer: {question}
"""
prompt = ChatPromptTemplate.from_template(template)
chain = prompt | model

while True:
    engine = pyttsx3.init()
    with mic as source:
        print("\n🎤 Listening... Speak now (say 'q' to quit)")
        recognizer.adjust_for_ambient_noise(source, duration=0.5)
        audio = recognizer.listen(source, timeout=10, phrase_time_limit=10)

        print("⏹️ Processing speech...")
        question = recognizer.recognize_google(audio)
        print(f"🗣️ You asked: {question}")
    print("\n-------------------------------")
    # question = input("Ask your question (q to quit): ")
    print("\n")
    if question == "q":
        break
    
    
    
    wiki = retriever.invoke(question)
    result = chain.invoke({"wiki": wiki, "question": question})
    print("\n-------------------------------")
    print(result)
    voices = engine.getProperty('voices') 
    engine.setProperty('voice', voices[1].id)
    engine.say(result)