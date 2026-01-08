import os
import pymongo
from bson import ObjectId
from datetime import datetime
from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
import logging

# FastAPI utils
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# LangChain
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain.prompts import ChatPromptTemplate
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi.responses import JSONResponse


# -------------------------------------------------------
# CONFIG
# -------------------------------------------------------
logging.basicConfig(level=logging.INFO)
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PDF_DIR = "data"
FAISS_DIR = "faiss_store"

# -------------------------------------------------------
# DATABASE
# -------------------------------------------------------
client = pymongo.MongoClient("mongodb://localhost:27017")
db = client["project"]
chats = db["chats"]

# -------------------------------------------------------
# FASTAPI APP
# ----------------------------------------------------
app=FastAPI()
limiter = Limiter(key_func=get_remote_address)




# -------------------------------------------------------
# REQUEST MODELS
# -------------------------------------------------------
class UserInput(BaseModel):
    query: str

class TitleUpdate(BaseModel):
    title: str

# -------------------------------------------------------
# LOAD & BUILD VECTOR STORE
# -------------------------------------------------------
if not os.path.exists(FAISS_DIR):
    all_docs = []

    for file in os.listdir(PDF_DIR):
        if not file.endswith(".pdf"):
            continue

        path = os.path.join(PDF_DIR, file)

        if os.path.getsize(path) < 1000:
            continue

        try:
            docs = PyPDFLoader(path).load()
            all_docs.extend(docs)
            print(f"Loaded: {file}")
        except Exception as e:
            print(f"Skipped {file}: {e}")

    if not all_docs:
        raise RuntimeError("No valid PDFs found.")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=150
    )

    chunks = splitter.split_documents(all_docs)

    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    vectorstore = FAISS.from_documents(chunks, embeddings)
    vectorstore.save_local(FAISS_DIR)

else:
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    vectorstore = FAISS.load_local(
        FAISS_DIR,
        embeddings,
        allow_dangerous_deserialization=True
    )

retriever = vectorstore.as_retriever(search_kwargs={"k": 5})
qa_prompt = ChatPromptTemplate.from_messages([
    ("system",
     "You are an AI assistant specialized in maternal health education. "
     "Provide general, educational information only. "
     " If the answer is partially available across multiple documents, you MAY summarize and combine information logically."
     "If the answer is not clearly stated in the documents, provide a GENERAL EDUCATIONAL explanation and clearly mention that it is general information."
     " Do NOT provide diagnosis, treatment, prescriptions, or emergency medical advice."
    " Do NOT invent facts that contradict the documents."
     "Do NOT give diagnosis, treatment, or emergency instructions. "
     "If information is missing, give general educational guidance."),
    ("human",
     "Context:\n{context}\n\nQuestion:\n{question}")
])


# -------------------------------------------------------
# LLM + RETRIEVAL QA
# -------------------------------------------------------
llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0,
    api_key=OPENAI_API_KEY
)


# -------------------------------------------------------
# EMERGENCY FILTER
# -------------------------------------------------------
EMERGENCY_KEYWORDS = [
    "heavy bleeding", "severe pain", "unconscious",
    "seizure", "cannot breathe", "emergency", "miscarriage"
]

def is_emergency(q: str) -> bool:
    return any(k in q.lower() for k in EMERGENCY_KEYWORDS)

# -------------------------------------------------------
# ROUTES
# -------------------------------------------------------
@app.post("/chat/new")
def new_chat():
    result = chats.insert_one({
        "title": "New Chat",
        "created_at": datetime.now(),
        "messages": []
    })
    return {"chat_id": str(result.inserted_id)}

@app.post("/chat/{chat_id}/send")
@limiter.limit("8/minute")
def send_message(chat_id: str, u: UserInput,request: Request):

    query = u.query.strip()

    # Create or validate chat
    if not chat_id or chat_id in ["null", "undefined"]:
        oid = chats.insert_one({
            "title": "New Chat",
            "created_at": datetime.now(),
            "messages": []
        }).inserted_id
    else:
        try:
            oid = ObjectId(chat_id)
        except:
            raise HTTPException(status_code=400, detail="Invalid chat ID")

    # Save user message
    chats.update_one(
        {"_id": oid},
        {"$push": {"messages": {"role": "user", "text": query}}}
    )

    # 🚨 Emergency check
    if is_emergency(query) and "what" not in query.lower():
        answer = (
            "This may be a medical emergency. "
            "Please seek immediate medical care or consult a healthcare professional."
        )
    else:
        try:
            docs = retriever.invoke(query)
            context = "\n\n".join(d.page_content for d in docs)

            if context.strip():
                messages = qa_prompt.format_messages(
                    context=context,
                    question=query
                )
                response = llm.invoke(messages)
                answer = response.content
            else:
                # fallback: general maternal health education
                answer = llm.invoke(
                    f"Provide general educational information about: {query}"
                ).content

        except Exception as e:
            logging.error(str(e))
            answer = (
                "Sorry, I couldn't process your question right now. "
                "Please try again."
            )

    # Save assistant message
    chats.update_one(
        {"_id": oid},
        {"$push": {"messages": {"role": "assistant", "text": answer}}}
    )

    return {"bot": answer}



@app.get("/chat/{chat_id}")
def get_chat(chat_id: str):
    oid = ObjectId(chat_id)
    chat = chats.find_one({"_id": oid})
    chat["_id"] = str(chat["_id"])
    return chat

@app.get("/chats")
def list_chats():
    return [
        {"chat_id": str(c["_id"]), "title": c.get("title", "Untitled")}
        for c in chats.find().sort("created_at", -1)
    ]

@app.put("/chat/{chat_id}/title")
def update_chat_title(chat_id: str, t: TitleUpdate):
    chats.update_one(
        {"_id": ObjectId(chat_id)},
        {"$set": {"title": t.title}}
    )
    return {"status": "updated"}

@app.delete("/chat/{chat_id}")
def delete_chat(chat_id: str):
    chats.delete_one({"_id": ObjectId(chat_id)})
    return {"status": "deleted"}

