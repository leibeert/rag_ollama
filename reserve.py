import streamlit as st
import hashlib
import ollama
import sqlite3
from datetime import datetime
from langdetect import detect
from PyPDF2 import PdfReader
from docx import Document
import io
from rag import RAGProcessor


PDF_DIR = "pdf_documents"
CHROMA_DIR = "chroma_db"

def init_db():
    conn = sqlite3.connect('chat_history.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS conversations(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            type TEXT DEFAULT 'normal',
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS messages(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            conversation_id INTEGER,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (conversation_id) REFERENCES conversations(id)
        )
    ''')
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
    msgs = [{"role": role, "content": content} for role, content in c.fetchall()]
    conn.close()
    return msgs

def save_message(user_id, conversation_id, role, content):
    conn, c = init_db()
    c.execute('''INSERT INTO messages (user_id, conversation_id, role, content, timestamp)
                 VALUES (?, ?, ?, ?, ?)''',
              (user_id, conversation_id, role, content, datetime.now()))
    conn.commit()
    conn.close()

def create_conversation(user_id, title, ctype='normal'):
    conn, c = init_db()
    c.execute('''INSERT INTO conversations(user_id, title, created_at, type)
                 VALUES(?, ?, CURRENT_TIMESTAMP, ?)''',
              (user_id, title, ctype))
    new_id = c.lastrowid
    conn.commit()
    conn.close()
    return new_id

def delete_conversation(conversation_id):
    conn, c = init_db()
    c.execute('DELETE FROM messages WHERE conversation_id = ?', (conversation_id,))
    c.execute('DELETE FROM conversations WHERE id = ?', (conversation_id,))
    conn.commit()
    conn.close()

def rename_conversation(conversation_id, new_title):
    conn, c = init_db()
    c.execute('UPDATE conversations SET title = ? WHERE id = ?', (new_title, conversation_id))
    conn.commit()
    conn.close()

def get_user_conversations(user_id, ctype='normal'):
    conn, c = init_db()
    c.execute('''SELECT id, title, created_at 
                 FROM conversations 
                 WHERE user_id = ? AND type = ?
                 ORDER BY created_at DESC''',
              (user_id, ctype))
    data = c.fetchall()
    conn.close()
    return data

def process_document(uploaded_file):
    if not uploaded_file:
        return ""
    file_type = uploaded_file.name.split('.')[-1].lower()
    try:
        if file_type == 'pdf':
            reader = PdfReader(uploaded_file)
            text = ""
            for page in reader.pages:
                text += page.extract_text() or ""
            return text
        elif file_type == 'txt':
            return uploaded_file.read().decode('utf-8')
        elif file_type == 'docx':
            doc = Document(uploaded_file)
            texts = [p.text for p in doc.paragraphs]
            return "\n".join(texts)
    except Exception as e:
        st.error(f"Error processing file: {str(e)}")
    return ""

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
                    with st.spinner("Initializing chat system..."):
                        st.session_state['user_id'] = user_id
                        st.session_state['username'] = username
                        # Initialize RAG only after successful login
                        if 'rag_processor' not in st.session_state:
                            st.session_state['rag_processor'] = RAGProcessor()
                    st.rerun()
                else:
                    st.error("Invalid username or password")
                    
        with tab2:
            new_user = st.text_input("Username", key="register_username")
            new_pass = st.text_input("Password", type="password", key="register_password")
            if st.button("Register"):
                if new_user and new_pass:
                    if create_user(new_user, new_pass):
                        st.success("User created successfully!")
                    else:
                        st.error("Username already exists.")
        return False
    return True

def display_normal_chat():
    st.sidebar.title("Conversations")
    if st.sidebar.button("New Conversation"):
        cid = create_conversation(st.session_state['user_id'],
                                  datetime.now().strftime("%Y-%m-%d %H:%M"),
                                  'normal')
        st.session_state['current_conversation'] = cid
        st.session_state['messages'] = []
        st.rerun()
    
    convos = get_user_conversations(st.session_state['user_id'], 'normal')
    for cid, title, _ in convos:
        col1, col2, col3 = st.sidebar.columns([2, 1, 1])
        with col1:
            if st.button(title, key=f"conv_{cid}"):
                st.session_state['current_conversation'] = cid
                st.session_state['messages'] = load_messages(
                    st.session_state['user_id'],
                    cid
                )
                st.rerun()
        with col2:
            if st.button("✏️", key=f"rename_{cid}"):
                new_title = st.text_input("New Title:", title, key=f"rename_input_{cid}")
                if st.button("Save Rename", key=f"save_rename_{cid}"):
                    rename_conversation(cid, new_title)
                    st.rerun()
        with col3:
            if st.button("🗑️", key=f"delete_{cid}"):
                delete_conversation(cid)
                if 'current_conversation' in st.session_state and st.session_state['current_conversation'] == cid:
                    st.session_state.pop('current_conversation', None)
                st.rerun()

    if st.sidebar.button("Logout"):
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        st.rerun()

    if "current_conversation" not in st.session_state:
        st.info("Select or create a new conversation.")
        return

    # Load messages when conversation is selected
    if "messages" not in st.session_state:
        st.session_state['messages'] = load_messages(
            st.session_state['user_id'],
            st.session_state['current_conversation']
        ) or []

    # Display all messages
    for msg in st.session_state['messages']:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    def generate_response():
        try:
            user_message = st.session_state.messages[-1]["content"]
            is_french = detect(user_message) == 'fr'
            
            document_context = st.session_state.get('document_content', '')
            
            if "fiche" in user_message.lower():
                content_start = user_message.lower().find("fiche") + len("fiche")
                user_content = user_message[content_start:].strip()
                fiche_content = generate_fiche_content(user_content)
                st.session_state["full_message"] = fiche_content
                yield fiche_content
            else:
                system_msg = "Répondez en français." if is_french else "Respond in English."
                
                messages = [
                    {"role": "system", "content": system_msg}
                ]
                
                if document_context:
                    messages.append({
                        "role": "system", 
                        "content": f"Contexte du document uploadé: {document_context[:1000]}"
                    })
                
                messages.extend(st.session_state.messages[-5:])

                try:
                    response = ollama.chat(
                        model='mistral:7B', 
                        stream=True, 
                        messages=messages,
                        options={"num_ctx": 2048}
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
        # Add and save user message
        st.session_state.messages.append({"role": "user", "content": prompt})
        save_message(
            st.session_state['user_id'],
            st.session_state['current_conversation'],
            "user",
            prompt
        )
        
        # Display user message
        with st.chat_message("user", avatar="🧑‍💻"):
            st.markdown(prompt)
        
        # Generate and display assistant response
        with st.chat_message("assistant", avatar="🤖"):
            st.write_stream(generate_response)
        
        # Save assistant response after generation is complete
        response_content = st.session_state["full_message"]
        st.session_state.messages.append({"role": "assistant", "content": response_content})
        save_message(
            st.session_state['user_id'],
            st.session_state['current_conversation'],
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
# Add generate_fiche_content function
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
    response = ollama.chat(model='mistral:7B', messages=[{"role": "user", "content": prompt}])
    return response['message']['content']



def display_rag_chat():
    st.title("Document Chat")

    # Sidebar for conversation management
    with st.sidebar:
        st.title("Conversations")
        
        # New conversation button
        if st.button("New Conversation"):
            cid = create_conversation(
                st.session_state['user_id'],
                "New RAG Chat",
                'rag'
            )
            st.session_state['current_conversation'] = cid
            st.session_state['messages'] = []
            st.rerun()

        # List existing conversations
        convos = get_user_conversations(st.session_state['user_id'], 'rag')

        # Store rename states in session state
        if 'rename_states' not in st.session_state:
            st.session_state['rename_states'] = {}

        # Display conversations
        for cid, title, _ in convos:
            col1, col2, col3 = st.columns([2, 1, 1])
            
            with col1:
                if st.button(title, key=f"r_{cid}"):
                    st.session_state['current_conversation'] = cid
                    st.session_state['messages'] = load_messages(
                        st.session_state['user_id'],
                        cid
                    )
                    st.rerun()
            
            with col2:
                # Toggle rename state
                if st.button("✏️", key=f"rename_r_{cid}"):
                    st.session_state['rename_states'][cid] = True
                
                # Show rename input and save button if in rename state
                if st.session_state['rename_states'].get(cid, False):
                    new_title = st.text_input("New Title:", title, key=f"rename_r_input_{cid}")
                    if st.button("Save", key=f"save_rename_r_{cid}"):
                        rename_conversation(cid, new_title)
                        st.session_state['rename_states'][cid] = False
                        st.rerun()
                    if st.button("Cancel", key=f"cancel_rename_r_{cid}"):
                        st.session_state['rename_states'][cid] = False
                        st.rerun()
            
            with col3:
                if st.button("🗑️", key=f"delete_r_{cid}"):
                    delete_conversation(cid)
                    if 'current_conversation' in st.session_state and st.session_state['current_conversation'] == cid:
                        st.session_state.pop('current_conversation', None)
                        st.session_state['messages'] = []
                    st.rerun()

    # Main chat area
    if 'current_conversation' not in st.session_state:
        st.info("Please select or create a conversation to start chatting")
        return

    # Initialize or load messages
    if 'messages' not in st.session_state:
        st.session_state['messages'] = load_messages(
            st.session_state['user_id'],
            st.session_state['current_conversation']
        ) or []

    # Display messages
    for message in st.session_state['messages']:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Chat input
    if prompt := st.chat_input("Ask about documents..."):
        # Display and save user message
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Save user message to database and session state
        save_message(
            st.session_state['user_id'],
            st.session_state['current_conversation'],
            "user",
            prompt
        )
        st.session_state['messages'].append({"role": "user", "content": prompt})
        
        try:
            with st.spinner("Thinking..."):
                # Get context and generate response
                context = st.session_state['rag_processor'].get_context(prompt)
                response = ollama.chat(
                    model='mistral:7B',
                    messages=[
                        {"role": "system", "content": f"Context: {context}"},
                        {"role": "user", "content": prompt}
                    ]
                )
                
                answer = response['message']['content']
                
                # Display and save assistant response
                with st.chat_message("assistant"):
                    st.markdown(answer)
                
                # Save assistant message to database and session state
                save_message(
                    st.session_state['user_id'],
                    st.session_state['current_conversation'],
                    "assistant",
                    answer
                )
                st.session_state['messages'].append({"role": "assistant", "content": answer})
                
        except Exception as e:
            st.error(f"Error: {str(e)}")

def generate_response(user_message):
    try:
        is_french = detect(user_message) == 'fr'
        document_context = st.session_state.get('document_content', '')

        # Handle "bonjour" specifically
        if user_message.strip().lower() == "bonjour":
            username = st.session_state.get('username', 'Utilisateur')
            return f"Bonjour {username}, je suis à votre service."

        # Proceed with RAG for other messages
        system_msg = "Répondez en français." if is_french else "Respond in English."

        messages = [
            {"role": "system", "content": system_msg}
        ]

        if document_context:
            messages.append({
                "role": "system",
                "content": f"Contexte du document uploadé: {document_context[:1000]}"
            })

        # Include recent messages as context
        messages.extend(st.session_state['messages'][-5:])

        response = ollama.chat(
            model='mistral:7B',
            messages=messages
        )
        return response['message']['content']

    except Exception as e:
        return f"Une erreur s'est produite: {str(e)}"

def main():
    st.title("ici le titre")
    col_left, col_right = st.columns([3, 1])
    with col_right:
        st.image("inverted-index.png", use_column_width=True)
    if not login_page():
        return
    
    if "chat_mode" not in st.session_state:
        st.session_state["chat_mode"] = "normal"

    with st.sidebar:
        st.title("Chat Mode")
        mode = st.radio("Select Mode:", ["Normal Chat", "Document Chat (RAG)"], key="mode_selection")
        if mode != st.session_state["chat_mode"]:
            st.session_state["chat_mode"] = "Normal Chat" if mode == "Normal Chat" else "Document Chat (RAG)"
            st.session_state.pop('document_content', None)
            st.session_state.pop('current_conversation', None)
            st.session_state['messages'] = []
            st.rerun()

    if st.session_state["chat_mode"] == "Normal Chat":
        display_normal_chat()
    else:
        display_rag_chat()

if __name__ == "__main__":
    main()