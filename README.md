Maternal Health RAG System

This project is a Retrieval-Augmented Generation (RAG) system designed to provide reliable, context-aware maternal health information by combining large language models with a vector-based retrieval pipeline.

The system ingests maternal health documents, converts them into vector embeddings, stores them in a FAISS vector database, and retrieves the most relevant context to generate accurate, grounded responses using LangChain. A FastAPI backend exposes the system as a scalable API, while MongoDB is used for storing metadata, user queries, and conversation history.
