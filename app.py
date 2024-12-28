import streamlit as st
import hashlib
import ollama
from langdetect import detect
import sqlite3
from datetime import datetime
from PyPDF2 import PdfReader
from docx import Document
import io
from rag import RAGProcessor


# rag = RAGProcessor()

# Enhanced database setup
def init_db():
    conn = sqlite3.connect('chat_history.db')
    c = conn.cursor()
    
    # Create users table if not exists
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  username TEXT UNIQUE NOT NULL,
                  password TEXT NOT NULL)''')

    # Create conversations table if not exists
    c.execute('''CREATE TABLE IF NOT EXISTS conversations
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER NOT NULL,
                  title TEXT NOT NULL,
                  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                  type TEXT DEFAULT 'normal',
                  FOREIGN KEY (user_id) REFERENCES users(id))''')

    # Create messages table with conversation_id included
    c.execute('''CREATE TABLE IF NOT EXISTS messages
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER NOT NULL,
                  role TEXT NOT NULL,
                  content TEXT NOT NULL,
                  conversation_id INTEGER,
                  timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                  FOREIGN KEY (user_id) REFERENCES users(id),
                  FOREIGN KEY (conversation_id) REFERENCES conversations(id))''')
    
    conn.commit()
    return conn, c

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def create_user(username, password):
    conn, c = init_db()
    try:
        c.execute('INSERT INTO users (username, password) VALUES (?, ?)',
                 (username, hash_password(password)))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def verify_user(username, password):
    conn, c = init_db()
    c.execute('SELECT id, password FROM users WHERE username = ?', (username,))
    result = c.fetchone()
    conn.close()
    if result and result[1] == hash_password(password):
        return result[0]
    return None

def load_messages(user_id, conversation_id=None):
    conn, c = init_db()
    try:
        if conversation_id:
            c.execute('''SELECT role, content 
                        FROM messages 
                        WHERE user_id = ? AND conversation_id = ? 
                        ORDER BY timestamp''', 
                        (user_id, conversation_id))
        else:
            c.execute('''SELECT role, content 
                        FROM messages 
                        WHERE user_id = ? 
                        ORDER BY timestamp''', 
                        (user_id,))
        
        messages = [{"role": role, "content": content} 
                   for role, content in c.fetchall()]
        return messages
    finally:
        conn.close()

def save_message(user_id, conversation_id, role, content):
    conn, c = init_db()
    c.execute('''INSERT INTO messages (user_id, conversation_id, role, content, timestamp)
                 VALUES (?, ?, ?, ?, ?)''', 
              (user_id, conversation_id, role, content, datetime.now()))
    conn.commit()
    conn.close()

def create_conversation(user_id, title):
    conn, c = init_db()
    try:
        c.execute('''INSERT INTO conversations 
                    (user_id, title, created_at) 
                    VALUES (?, ?, CURRENT_TIMESTAMP)''', 
                    (user_id, title))
        conn.commit()
        return c.lastrowid
    finally:
        conn.close()

def delete_conversation(conversation_id):
    conn, c = init_db()
    try:
        c.execute('DELETE FROM messages WHERE conversation_id = ?', (conversation_id,))
        c.execute('DELETE FROM conversations WHERE id = ?', (conversation_id,))
        conn.commit()
    finally:
        conn.close()

def get_user_conversations(user_id):
    conn, c = init_db()
    try:
        c.execute('''SELECT id, title, created_at 
                    FROM conversations 
                    WHERE user_id = ? 
                    ORDER BY created_at DESC''', (user_id,))
        return c.fetchall()
    finally:
        conn.close()

def rename_conversation(conversation_id, new_title):
    conn, c = init_db()
    try:
        c.execute('''UPDATE conversations 
                     SET title = ? 
                     WHERE id = ?''', (new_title, conversation_id))
        conn.commit()
    finally:
        conn.close()

def process_document(uploaded_file):
    if uploaded_file is not None:
        file_content = ""
        file_type = uploaded_file.name.split('.')[-1].lower()
        
        try:
            if file_type == 'pdf':
                pdf_reader = PdfReader(uploaded_file)
                for page in pdf_reader.pages:
                    file_content += page.extract_text()
            
            elif file_type == 'txt':
                file_content = uploaded_file.getvalue().decode('utf-8')
            
            elif file_type == 'docx':
                doc = Document(io.BytesIO(uploaded_file.getvalue()))
                for para in doc.paragraphs:
                    file_content += para.text + '\n'
            
            return file_content.strip()
        except Exception as e:
            st.error(f"Error processing file: {str(e)}")
            return ""
    return ""

# Login interface
def login_page():
    if 'user_id' not in st.session_state:
        st.title("Login")
        
        tab1, tab2 = st.tabs(["Login", "Register"])
        
        with tab1:
            username = st.text_input("Username", key="login_username")
            password = st.text_input("Password", type="password", key="login_password")
            if st.button("Login"):
                user_id = verify_user(username, password)
                if user_id:
                    st.session_state['user_id'] = user_id
                    st.session_state['username'] = username
                else:
                    st.error("Invalid credentials")
        
        with tab2:
            new_username = st.text_input("Username", key="register_username")
            new_password = st.text_input("Password", type="password", key="register_password")
            if st.button("Register"):
                if create_user(new_username, new_password):
                    st.success("Registration successful! Please login.")
                else:
                    st.error("Username already exists")
        return False
    return True

def generate_fiche_content(user_content):
    template = """Sur la base de cette entrée : "{user_content}", générez une fiche administrative française formelle qui ressemble exactement à ceci :

A Rabat le,  09.08.2024
ROYAUME DU MAROC
XXXXXXXXX
XXXXXXX
XXXXX
DIVISION "I"

FICHE

A L'ATTENTION DE MONSIEUR LE GENERAL DE DIVISION, 
CHEF DU XXXXXXX.

[Generate appropriate content here maintaining this structure:
- Objet: (related to the input)
- Référence: (appropriate reference number)
- Detailed content and context
- Any conclusions or recommendations]

Respectueusement,
Le Capitaine XXXXXXXX, de la Division
Informatique du XXXXX.

SIGNE : XXXXXXXXX"""
    
    prompt = template.format(user_content=user_content)
    response = ollama.chat(model='llama3', messages=[{"role": "user", "content": prompt}])
    return response['message']['content']

def main():
    col_left, col_right = st.columns([3, 1])
    with col_right:
        st.image("inverted-index.png", use_column_width=True)
    if 'rag_processor' not in st.session_state:
        st.session_state['rag_processor'] = RAGProcessor()
        
    if not login_page():
        return

    if st.session_state.get("user_id"):
        # Add mode selection after login
        if "chat_mode" not in st.session_state:
            st.session_state["chat_mode"] = "normal"
        
        # Mode selection in sidebar
        with st.sidebar:
            st.title("Chat Mode")
            mode = st.radio(
                "Select Mode:",
                ["Normal Chat", "Document Chat (RAG)"],
                key="mode_selection"
            )
            
            if mode != st.session_state["chat_mode"]:
                st.session_state["chat_mode"] = mode
                st.session_state["messages"] = []  # Clear messages on mode switch
                st.rerun()

        # Display appropriate chat interface based on mode
        if st.session_state["chat_mode"] == "Normal Chat":
            display_normal_chat()
        else:
            display_rag_chat()

def display_normal_chat():
    # Sidebar conversation management
    st.sidebar.title("Conversations")
    
    # New conversation button
    if st.sidebar.button("New Conversation"):
        title = datetime.now().strftime("%Y-%m-%d %H:%M")
        conv_id = create_conversation(st.session_state['user_id'], title)
        st.session_state['current_conversation'] = conv_id
        st.session_state['messages'] = []
        st.session_state.pop('document_content', None)  # Clear any previous document content
        st.rerun()

    # List conversations with rename option
    conversations = get_user_conversations(st.session_state['user_id'])
    for conv_id, title, created_at in conversations:
        col1, col2, col3 = st.sidebar.columns([2, 1, 1])
        
        with col1:
            if st.button(f"📝 {title}", key=f"conv_{conv_id}"):
                st.session_state['current_conversation'] = conv_id
                st.session_state['messages'] = load_messages(
                    st.session_state['user_id'], 
                    conv_id
                )
                st.session_state.pop('document_content', None)  # Clear any previous document content
                st.rerun()
                
        with col2:
            if st.button("✏️", key=f"edit_{conv_id}"):
                st.session_state['editing_conversation'] = conv_id
                st.session_state['edit_title'] = title
                
        with col3:
            if st.button("🗑️", key=f"del_{conv_id}"):
                delete_conversation(conv_id)
                if 'current_conversation' in st.session_state:
                    del st.session_state['current_conversation']
                st.session_state.pop('document_content', None)  # Clear any previous document content
                st.rerun()
        
        # Show edit field if editing this conversation
        if st.session_state.get('editing_conversation') == conv_id:
            new_title = st.sidebar.text_input(
                "New title",
                value=st.session_state['edit_title'],
                key=f"new_title_{conv_id}"
            )
            col1, col2 = st.sidebar.columns([1, 1])
            with col1:
                if st.button("Save", key=f"save_{conv_id}"):
                    rename_conversation(conv_id, new_title)
                    del st.session_state['editing_conversation']
                    st.rerun()
            with col2:
                if st.button("Cancel", key=f"cancel_{conv_id}"):
                    del st.session_state['editing_conversation']
                    st.rerun()

    # Logout button
    if st.sidebar.button("Logout"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

    # Chat interface
    if "current_conversation" not in st.session_state:
        st.info("Please select or create a new conversation")
        return

    # Load user's chat history
    if "messages" not in st.session_state:
        stored_messages = load_messages(
            st.session_state['user_id'], 
            st.session_state.get('current_conversation')
        )
        if stored_messages:
            st.session_state["messages"] = stored_messages
        else:
            st.session_state["messages"] = [{"role": "assistant", 
                "content": f"Bonjour {st.session_state['username']}, comment puis-je vous aider?"}]

    # Write Message History
    for msg in st.session_state.messages:
        if msg["role"] == "user":
            st.chat_message(msg["role"], avatar="🧑‍💻").write(msg["content"])
        else:
            st.chat_message(msg["role"], avatar="🤖").write(msg["content"])

    def generate_response():
        try:
            user_message = st.session_state.messages[-1]["content"]
            is_french = detect(user_message) == 'fr'
            
            # Check if document content is available
            document_context = st.session_state.get('document_content', '')
            
            if "fiche" in user_message.lower():
                content_start = user_message.lower().find("fiche") + len("fiche")
                user_content = user_message[content_start:].strip()
                fiche_content = generate_fiche_content(user_content)
                st.session_state["full_message"] = fiche_content
                yield fiche_content
            else:
                system_msg = "Répondez en français." if is_french else "Respond in English."
                
                # Modify messages to include document context if available
                messages = [
                    {"role": "system", "content": system_msg}
                ]
                
                if document_context:
                    messages.append({
                        "role": "system", 
                        "content": f"Contexte du document uploadé: {document_context[:1000]}"  # Limit context to first 1000 characters
                    })
                
                messages.extend(st.session_state.messages[-5:])  # Limit context window

                try:
                    response = ollama.chat(
                        model='mistral:7B', 
                        stream=True, 
                        messages=messages,
                        options={"num_ctx": 2048}  # Set context window
                    )
                    st.session_state["full_message"] = ""
                    for partial_resp in response:
                        token = partial_resp["message"]["content"]
                        st.session_state["full_message"] += token
                        yield token
                except Exception as e:
                    error_msg = f"Une erreur s'est produite: {str(e)}"
                    st.session_state["full_message"] = error_msg
                    yield error_msg
                
        except Exception as e:
            error_msg = f"Une erreur s'est produite: {str(e)}"
            st.session_state["full_message"] = error_msg
            yield error_msg

    if prompt := st.chat_input("What is up?"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        save_message(
            st.session_state['user_id'], 
            st.session_state.get('current_conversation'),
            "user", 
            prompt
        )
        st.chat_message("user", avatar="🧑‍💻").write(prompt)
        st.chat_message("assistant", avatar="🤖").write_stream(generate_response)
        
        # After generating response
        response_content = st.session_state["full_message"]
        st.session_state.messages.append({"role": "assistant", "content": response_content})
        save_message(
            st.session_state['user_id'], 
            st.session_state.get('current_conversation'),
            "assistant", 
            response_content
        )

    # File uploader
    uploaded_file = st.file_uploader("Upload a document (PDF, TXT, DOCX)", 
                                    type=['pdf', 'txt', 'docx'])

    if uploaded_file:
        document_content = process_document(uploaded_file)
        st.session_state['document_content'] = document_content
        st.success(f"Document '{uploaded_file.name}' uploaded successfully!")

def display_rag_chat():
    st.title("Document Chat")

    # Sidebar for conversation management
    with st.sidebar:
        st.title("Conversations")
        
        # New conversation button
        if st.button("New Conversation"):
            conn, c = init_db()
            c.execute('''INSERT INTO conversations (user_id, title, created_at, type)
                        VALUES (?, ?, ?, ?)''', 
                     (st.session_state['user_id'], "New RAG Chat", datetime.now(), 'rag'))
            new_conv_id = c.lastrowid
            conn.commit()
            conn.close()
            st.session_state['current_conversation'] = new_conv_id
            st.session_state['messages'] = []
            st.rerun()

        # List only RAG conversations
        conn, c = init_db()
        c.execute('''SELECT id, title FROM conversations 
                    WHERE user_id = ? AND type = 'rag' 
                    ORDER BY created_at DESC''', 
                 (st.session_state['user_id'],))
        conversations = c.fetchall()
        conn.close()

        for conv_id, title in conversations:
            col1, col2, col3 = st.columns([3, 1, 1])
            
            with col1:
                if st.button(title, key=f"conv_{conv_id}"):
                    st.session_state['current_conversation'] = conv_id
                    st.session_state['messages'] = []
                    st.rerun()
            
            with col2:
                if st.button("✏️", key=f"rename_{conv_id}"):
                    new_title = st.text_input("New title:", title, key=f"new_title_{conv_id}")
                    if st.button("Save", key=f"save_{conv_id}"):
                        conn, c = init_db()
                        c.execute('''UPDATE conversations SET title = ? WHERE id = ?''', 
                                (new_title, conv_id))
                        conn.commit()
                        conn.close()
                        st.rerun()
            
            with col3:
                if st.button("🗑️", key=f"delete_{conv_id}"):
                    if st.button("Confirm Delete", key=f"confirm_{conv_id}"):
                        conn, c = init_db()
                        c.execute('''DELETE FROM messages WHERE conversation_id = ?''', (conv_id,))
                        c.execute('''DELETE FROM conversations WHERE id = ?''', (conv_id,))
                        conn.commit()
                        conn.close()
                        if 'current_conversation' in st.session_state:
                            del st.session_state['current_conversation']
                        st.rerun()

    
    
    # Get or create conversation
    if 'current_conversation' not in st.session_state:
        conn, c = init_db()
        c.execute('''INSERT INTO conversations (user_id, title, created_at)
                     VALUES (?, ?, ?)''', 
                  (st.session_state['user_id'], "New RAG Chat", datetime.now()))
        st.session_state['current_conversation'] = c.lastrowid
        conn.commit()
        conn.close()

    # Load existing messages
    stored_messages = load_messages(
        st.session_state['user_id'], 
        st.session_state['current_conversation']
    )
    
    if stored_messages:
        st.session_state["messages"] = stored_messages
    
    # Display messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    
    # Chat input
    if prompt := st.chat_input("Ask about documents..."):
        with st.chat_message("user"):
            st.markdown(prompt)
            
        # Save user message
        save_message(
            st.session_state['user_id'],
            st.session_state['current_conversation'],
            "user",
            prompt
        )
        
        try:
            context = rag.get_context(prompt)
            response = ollama.chat(
                model='mistral',
                messages=[
                    {"role": "system", "content": f"Context: {context}"},
                    {"role": "user", "content": prompt}
                ]
            )
            
            answer = response['message']['content']
            
            with st.chat_message("assistant"):
                st.markdown(answer)
                
            # Save assistant message
            save_message(
                st.session_state['user_id'],
                st.session_state['current_conversation'],
                "assistant",
                answer
            )
            
        except Exception as e:
            st.error(f"Error: {str(e)}")

if __name__ == "__main__":
    main()