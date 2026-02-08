from fastapi import FastAPI, Depends, HTTPException, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional
import os
import uuid
from datetime import datetime, timedelta
import jwt
from passlib.context import CryptContext

from backend.auth import authenticate_user, create_access_token, get_current_user, pwd_context
from backend.db.database import engine, SessionLocal, get_db
from backend.models.user import User
from backend.schemas.user import UserCreate, UserResponse
from backend.ingestion.excel_to_db import process_excel_file
from backend.ingestion.pdf_to_db import process_pdf_file
from backend.rag.rag_pipeline import RAGPipeline
from backend.utils.file_handler import allowed_file_type, save_uploaded_file

app = FastAPI(title="Banking RAG Chatbot API")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize RAG pipeline
rag_pipeline = RAGPipeline()

# Create tables
from backend.models.base import Base
Base.metadata.create_all(bind=engine)

@app.get("/")
def read_root():
    return {"message": "Banking RAG Chatbot API"}

@app.post("/register")
async def register_user(user: UserCreate, db: Session = Depends(get_db)):
    """Register a new user"""
    # Validate email format
    if not user.email or "@" not in user.email or user.email.lower() != user.email:
        raise HTTPException(status_code=400, detail="Invalid email format. Email must be lowercase and contain @")
    
    # Validate password strength
    if len(user.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters long")
    
    has_uppercase = any(c.isupper() for c in user.password)
    has_lowercase = any(c.islower() for c in user.password)
    has_special = any(not c.isalnum() for c in user.password)
    
    if not (has_uppercase and has_lowercase and has_special):
        raise HTTPException(
            status_code=400, 
            detail="Password must contain at least 1 uppercase, 1 lowercase, and 1 special character"
        )
    
    # Check if user already exists
    existing_user = db.query(User).filter(User.email == user.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="User with this email already exists")
    
    # Hash password and create user
    hashed_password = pwd_context.hash(user.password)
    db_user = User(
        name=user.name,
        email=user.email,
        hashed_password=hashed_password
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    return UserResponse.from_orm(db_user)

@app.post("/login")
async def login_user(email: str, password: str, db: Session = Depends(get_db)):
    """Authenticate user and return access token"""
    user = authenticate_user(db, email, password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    access_token = create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Upload and process documents"""
    # Validate file type
    if not allowed_file_type(file.filename):
        raise HTTPException(status_code=400, detail="Unsupported file type. Only PDF and Excel files are allowed.")
    
    # Save uploaded file temporarily
    file_path = save_uploaded_file(file)
    
    try:
        # Process based on file type
        if file.filename.lower().endswith('.pdf'):
            await process_pdf_file(file_path, current_user.id)
        elif file.filename.lower().endswith(('.xlsx', '.xls')):
            await process_excel_file(file_path, current_user.id)
        
        return {"message": "Document processed successfully", "filename": file.filename}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing document: {str(e)}")
    finally:
        # Clean up temporary file
        if os.path.exists(file_path):
            os.remove(file_path)

@app.post("/chat")
async def chat(
    message: str = Form(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Handle chat queries using RAG"""
    if not message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    
    # Check if query is related to banking domain
    banking_keywords = ["account", "transaction", "balance", "loan", "credit", "debit", "payment", "transfer", "bank"]
    is_banking_related = any(keyword.lower() in message.lower() for keyword in banking_keywords)
    
    if not is_banking_related:
        return {
            "response": "This chatbot is designed specifically for banking-related queries. "
                       "Please ask questions related to banking products, services, or policies."
        }
    
    # Use RAG pipeline to generate response
    try:
        response = rag_pipeline.generate_response(message, current_user.id)
        return {"response": response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating response: {str(e)}")

@app.get("/chat_history")
async def get_chat_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get chat history for current user"""
    # This would typically return stored chat history
    # Implementation depends on how you want to store chat history
    return {"history": []}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)