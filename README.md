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


## Running the Application

1. **Run the Setup Script**
    ```bash
    python main.py
    ```

2. **Start the Streamlit Application**
    ```bash
    streamlit run app.py
    ```

3. **Access the Application**
    Open your browser and navigate to [http://localhost:8501](http://localhost:8501)

## Usage

1. **Login/Register**
    - Create a new account or log in with existing credentials.
    - Passwords are securely hashed for protection.

2. **Chat Modes**
    - **Normal Chat**: Engage in standard AI conversations without any document context.
    - **Document Chat**: Upload documents to enable context-aware conversations based on the content of the uploaded files.

3. **Document Processing**
    - Upload PDF or DOCX files in Document Chat mode.
    - The system will automatically extract and process text from the uploaded documents.
    - Generate vector embeddings for efficient retrieval using ChromaDB.

4. **Conversation Management**
    - Create new conversations or continue existing ones.
    - Rename or delete conversations as needed.
    - Switch between multiple chat threads seamlessly.

## Dependencies

- **streamlit**: For building the web interface.
- **ollama**: For handling the AI models.
- **PyPDF2**: For PDF text extraction.
- **python-docx**: For DOCX text extraction.
- **langdetect**: For language detection.
- **chromaDB**: For vector-based document storage.
- **sentence-transformers**: For generating text embeddings.
- **sqlite3**: For managing chat history.

## Configuration

- **Server**: Runs on `localhost:8501` by default.
- **Database**: Uses SQLite (`chat_history.db`) for storing user data and chat history.
- **Vector Store**: Utilizes ChromaDB for storing document embeddings.
- **LLM**: Mistral 7B model accessed via Ollama.

## Notes

- Ensure Ollama is running before starting the application.
- Execute  once for the initial setup of the database and necessary directories.
- Uploaded documents are stored in the  directory and their embeddings in .
- Chat history is maintained in the SQLite database for future reference.

## License

MIT License


