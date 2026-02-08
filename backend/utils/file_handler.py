import os
import uuid
from typing import Union
from fastapi import UploadFile
import tempfile

def allowed_file_type(filename: str) -> bool:
    """
    Check if the file type is allowed
    """
    ALLOWED_EXTENSIONS = {'.pdf', '.xlsx', '.xls'}
    _, ext = os.path.splitext(filename.lower())
    return ext in ALLOWED_EXTENSIONS

def save_uploaded_file(file: UploadFile) -> str:
    """
    Save uploaded file to a temporary location and return the file path
    """
    # Generate a unique filename
    unique_filename = f"{uuid.uuid4()}_{file.filename}"
    
    # Create a temporary file
    temp_dir = tempfile.gettempdir()
    file_path = os.path.join(temp_dir, unique_filename)
    
    # Write the file content to the temporary file
    with open(file_path, "wb") as buffer:
        buffer.write(file.file.read())
    
    return file_path