from rag import initialize_rag

# Initialize the RAG processor
rag = initialize_rag()

# Process the PDFs and create the vector store
vector_store = rag.process_pdfs()

# Test a query
if vector_store:
    context = rag.get_context("your query here")
    print("Retrieved context:", context)