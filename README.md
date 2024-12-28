# rag_ollama
# RAG-Powered Chat Application

A sophisticated chat application that combines traditional chat functionality with RAG (Retrieval Augmented Generation) capabilities for document-based conversations.

## Features

- **Dual Chat Modes**
  - Normal Chat: Traditional conversational interface
  - Document Chat (RAG): AI-powered document context-aware conversations

- **User Management**
  - Secure user authentication
  - Password hashing
  - Session management

- **Conversation Management**
  - Create new conversations
  - Rename existing chats
  - Delete conversations
  - History preservation

- **Document Processing**
  - Supports PDF, DOCX, and TXT files
  - Document vectorization using ChromaDB
  - Semantic search capabilities
  - Context-aware responses

## Tech Stack

- **Frontend**: Streamlit
- **Database**: SQLite3 (chat history), ChromaDB (vector store)
- **AI Models**: 
  - Mistral-7B (via Ollama)
  - HuggingFace embeddings (sentence-transformers/all-MiniLM-L6-v2)
- **Document Processing**: PyPDF2, python-docx
- **Language Detection**: langdetect

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
