import chromadb
from sentence_transformers import SentenceTransformer
import numpy as np
from typing import List, Tuple, Dict, Any
import psycopg2
from sqlalchemy.orm import Session
import os

class RAGPipeline:
    def __init__(self):
        # Initialize embedding model
        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        
        # Initialize ChromaDB client
        self.chroma_client = chromadb.Client()
        
        # Create collection for embeddings
        self.collection = self.chroma_client.get_or_create_collection(name="document_chunks")
        
        # Database configuration
        self.db_config = {
            "host": "localhost",
            "database": "api_specs",
            "user": "postgres",
            "password": "admin123",
            "port": "5432"
        }
    
    def add_document_chunks(self, chunks: List[str], doc_metadata: Dict[str, Any]):
        """
        Add document chunks to the vector database
        """
        # Generate embeddings for the chunks
        embeddings = self.embedding_model.encode(chunks).tolist()
        
        # Prepare metadata for each chunk
        metadatas = [doc_metadata for _ in chunks]
        
        # Generate IDs for the chunks
        ids = [f"chunk_{i}" for i in range(len(chunks))]
        
        # Add to ChromaDB collection
        self.collection.add(
            embeddings=embeddings,
            metadatas=metadatas,
            ids=ids
        )
    
    def query_similar_chunks(self, query: str, top_k: int = 5) -> List[Tuple[str, float, Dict]]:
        """
        Find similar chunks based on the query
        Returns list of tuples: (chunk_text, similarity_score, metadata)
        """
        # Generate embedding for the query
        query_embedding = self.embedding_model.encode([query]).tolist()
        
        # Query the collection
        results = self.collection.query(
            query_embeddings=query_embedding,
            n_results=top_k
        )
        
        # Format results
        chunks_with_scores = []
        for i in range(len(results['documents'][0])):
            chunk_text = results['documents'][0][i]
            similarity_score = results['distances'][0][i]
            metadata = results['metadatas'][0][i]
            chunks_with_scores.append((chunk_text, similarity_score, metadata))
        
        return chunks_with_scores
    
    def query_database(self, query: str, user_id: int) -> List[Dict]:
        """
        Query the structured database (PostgreSQL) for API specs
        """
        conn = psycopg2.connect(**self.db_config)
        cur = conn.cursor()
        
        # Search for matching records based on the query
        # This is a simplified search - in production, you'd want more sophisticated search
        search_term = f"%{query}%"
        cur.execute("""
            SELECT field_name, api_name, full_path, parent_field_id
            FROM api_spec
            WHERE (field_name ILIKE %s OR api_name ILIKE %s OR full_path ILIKE %s)
            AND user_id = %s
            LIMIT 10
        """, (search_term, search_term, search_term, user_id))
        
        results = cur.fetchall()
        columns = [desc[0] for desc in cur.description]
        
        # Format results as list of dictionaries
        formatted_results = []
        for row in results:
            result_dict = {}
            for i, col in enumerate(columns):
                result_dict[col] = row[i]
            formatted_results.append(result_dict)
        
        cur.close()
        conn.close()
        
        return formatted_results
    
    def classify_query(self, query: str) -> str:
        """
        Classify the query to determine if it should go to SQL or semantic search
        Returns 'sql' or 'semantic'
        """
        # Keywords that suggest structured data lookup
        sql_keywords = [
            'field', 'column', 'table', 'api', 'endpoint', 'parameter', 
            'attribute', 'property', 'schema', 'structure', 'definition',
            'specification', 'level', 'hierarchy', 'parent', 'child'
        ]
        
        query_lower = query.lower()
        sql_matches = sum(1 for keyword in sql_keywords if keyword in query_lower)
        
        # If more than 2 SQL-related keywords, route to SQL
        if sql_matches >= 2:
            return 'sql'
        
        # Otherwise, use semantic search
        return 'semantic'
    
    def generate_response(self, query: str, user_id: int) -> str:
        """
        Main method to generate response using RAG
        """
        # Classify query to determine routing
        query_type = self.classify_query(query)
        
        if query_type == 'sql':
            # Query structured data (PostgreSQL)
            sql_results = self.query_database(query, user_id)
            
            if sql_results:
                # Format SQL results into a response
                response_parts = ["Based on the uploaded API specifications:"]
                for result in sql_results[:3]:  # Limit to first 3 results
                    response_parts.append(f"- {result.get('field_name', 'N/A')} in {result.get('api_name', 'N/A')}")
                return " ".join(response_parts)
            else:
                return "The requested information is not present in the uploaded documents."
        
        else:
            # Use semantic search (ChromaDB)
            similar_chunks = self.query_similar_chunks(query, top_k=5)
            
            if similar_chunks and similar_chunks[0][1] < 0.8:  # Distance threshold
                # Build context from similar chunks
                context_parts = ["Based on the uploaded documents:"]
                for chunk, score, metadata in similar_chunks[:3]:  # Top 3 chunks
                    context_parts.append(f"- {chunk}")
                
                # For a real implementation, you would send this context to an LLM
                # Here we'll simulate the response
                return " ".join(context_parts)
            else:
                return "The requested information is not present in the uploaded documents."
    
    def clear_database(self):
        """
        Clear the vector database (useful for testing)
        """
        self.chroma_client.delete_collection(name="document_chunks")
        self.collection = self.chroma_client.get_or_create_collection(name="document_chunks")