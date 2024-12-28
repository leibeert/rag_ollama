import os
import PyPDF2
import chromadb
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain.schema.document import Document
from typing import List, Optional

# Constants
PDF_DIR = "pdf_documents"
CHROMA_DIR = "chroma_db"

class RAGProcessor:
    def __init__(self):
        # print(f"Initializing RAGProcessor...")
        # print(f"PDF directory path: {os.path.abspath(PDF_DIR)}")
        # print(f"ChromaDB directory path: {os.path.abspath(CHROMA_DIR)}")
        
        self.embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2"
        )
        self.collection_name = "pdf_collection"
        self.vector_store = None
        
    def process_pdfs(self) -> Optional[Chroma]:
        # Ensure both directories exist
        os.makedirs(PDF_DIR, exist_ok=True)
        os.makedirs(CHROMA_DIR, exist_ok=True)
        
        all_texts = []
        all_metadata = []
        
        pdf_files = [f for f in os.listdir(PDF_DIR) if f.endswith('.pdf')]
        print(f"Found {len(pdf_files)} PDF files: {pdf_files}")
        
        if not pdf_files:
            print("No PDF files found in the directory")
            return None
            
        for filename in pdf_files:
            file_path = os.path.join(PDF_DIR, filename)
            print(f"Processing {filename}...")
            try:
                text = self._extract_text_from_pdf(file_path)
                print(f"Extracted {len(text)} characters from {filename}")
                if not text.strip():
                    print(f"Warning: No text extracted from {filename}")
                    continue
                    
                all_texts.append(text)
                all_metadata.append({"source": filename})
            except Exception as e:
                print(f"Error processing {filename}: {str(e)}")
                continue
        
        if not all_texts:
            print("No text was extracted from PDFs")
            return None
            
        print(f"Creating chunks from {len(all_texts)} documents...")
        documents = self._create_chunks(all_texts, all_metadata)
        print(f"Created {len(documents)} chunks")
        
        try:
            print("Initializing Chroma vector store...")
            self.vector_store = Chroma.from_documents(
                documents=documents,
                embedding=self.embeddings,
                persist_directory=CHROMA_DIR,
                collection_name=self.collection_name
            )
            
            # Explicitly persist the database
            print("Persisting vector store...")
            self.vector_store.persist()
            print(f"Vector store created and persisted to {CHROMA_DIR}")
            
            # Verify the database was created
            if os.path.exists(os.path.join(CHROMA_DIR, "chroma.sqlite3")):
                print("Successfully verified database file creation")
            else:
                print("Warning: Database file not found after creation")
                
            return self.vector_store
            
        except Exception as e:
            print(f"Error creating vector store: {str(e)}")
            return None

    def get_context(self, query: str, k: int = 3) -> str:
        """
        Retrieve context from the vector store based on a query.
        
        Args:
            query (str): The query text to search for
            k (int): Number of documents to retrieve
            
        Returns:
            str: Retrieved context as a string
        """
        if self.vector_store is None:
            if not os.path.exists(CHROMA_DIR):
                print("No existing vector store found")
                return ""
                
            self.vector_store = Chroma(
                collection_name=self.collection_name,
                embedding_function=self.embeddings,
                persist_directory=CHROMA_DIR
            )
        
        docs = self.vector_store.similarity_search(query, k=k)
        return "\n".join([doc.page_content for doc in docs])

    def _extract_text_from_pdf(self, file_path: str) -> str:
        with open(file_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            text = ""
            for page_num, page in enumerate(pdf_reader.pages):
                try:
                    page_text = page.extract_text()
                    text += page_text + " "
                    print(f"Extracted {len(page_text)} characters from page {page_num + 1}")
                except Exception as e:
                    print(f"Error extracting text from page {page_num + 1} in {file_path}: {str(e)}")
            return text.strip()
    
    def _create_chunks(self, texts: List[str], metadata: List[dict]) -> List[Document]:
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200
        )
        
        all_documents = []
        for text, meta in zip(texts, metadata):
            chunks = text_splitter.create_documents([text], [meta])
            print(f"Created {len(chunks)} chunks for document {meta['source']}")
            all_documents.extend(chunks)
            
        return all_documents

def initialize_rag():
    rag = RAGProcessor()
    if not os.path.exists(CHROMA_DIR):
        print("Initializing new vector store...")
        vector_store = rag.process_pdfs()
        if vector_store is None:
            print("Failed to create vector store")
    else:
        print("Using existing vector store")
    return rag