# Banking RAG Chatbot

A secure, on-premise RAG (Retrieval Augmented Generation) chatbot designed specifically for banking institutions. This system allows users to securely upload banking documents (PDFs/Excel) and ask questions about their content, with strict security measures to ensure sensitive data never leaves the organization.

## Architecture Overview

The system consists of two main components:
1. **PostgreSQL**: Stores structured API specifications and user data
2. **ChromaDB**: Stores embeddings of unstructured document content

### Key Features
- Secure document ingestion with user isolation
- Hierarchical API specification handling
- Rule-based query classification (SQL vs semantic)
- Strict banking domain focus
- Client authentication with JWT tokens
- Local-first approach (no external LLM dependencies)

## Tech Stack

**Backend:**
- Python 3.11
- FastAPI
- SQLAlchemy
- PostgreSQL
- ChromaDB
- SentenceTransformers (for embeddings)

**Frontend:**
- Pure HTML/CSS/JavaScript
- Responsive design

## Installation

1. Clone the repository
2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up PostgreSQL database with proper credentials
4. Run the application:
```bash
uvicorn backend.main:app --reload
```

## Running with Docker

Alternatively, you can run the entire stack using Docker Compose:

```bash
docker-compose up -d
```

The application will be accessible at http://localhost:8000

## Security Features

- All document processing happens locally
- No raw documents sent to external services
- User isolation with separate data spaces
- JWT-based authentication
- Strict input validation

## Usage

1. Register a new user account
2. Log in to the system
3. Upload banking documents (PDF or Excel)
4. Ask questions about the document content
5. Receive answers based on the uploaded documents

## Document Ingestion Rules

### Excel Files
- Automatically converted to SQL tables
- Hierarchical structures detected via "level" columns
- Deduplication and incremental updates

### PDF Files
- Tables extracted and converted to SQL
- Paragraph text converted to embeddings
- Continuation tables across pages merged

## Database Schema

The system maintains two databases:

### PostgreSQL Tables
- `users`: Authentication and user information
- `api_spec`: Structured API specifications with hierarchical relationships

### ChromaDB Collections
- `document_chunks`: Embeddings of unstructured document content

## Query Classification

The system uses rule-based classification to determine the appropriate response strategy:
- SQL queries: For structured data (API fields, parameters, etc.)
- Semantic queries: For unstructured content questions

## Development

To run in development mode with auto-reload:
```bash
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

## Production Deployment

For production deployment:
1. Change the SECRET_KEY environment variable
2. Configure proper PostgreSQL connection
3. Set up HTTPS termination
4. Adjust resource limits as needed

## License

This project is licensed under the MIT License.