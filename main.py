from langchain_ollama.llms import OllamaLLM
from langchain_core.prompts import ChatPromptTemplate
from vector import retriever
import speech_recognition as sr
import pyttsx3


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


retriever.search_kwargs["k"] = 5



while True:
    with mic as source:
        speak_ai("Ask me a question about Terraria!")
        print("\n🎤 Listening... (say 'q' to quit)")
        recognizer.adjust_for_ambient_noise(source, duration=0.5)
        audio = recognizer.listen(source, timeout=15, phrase_time_limit=30)

    try:
        question = recognizer.recognize_google(audio)
    except:
        continue

    if question.lower() == "q":
        break

    print(f"\n🗣️ You asked: {question}")

    docs = retriever.invoke(question)
    wiki = "\n\n".join(doc.page_content for doc in docs)

    answer = chain.invoke({"wiki": wiki, "question": question})
    speak_ai(answer)
    print("\n🤖", answer)
    
