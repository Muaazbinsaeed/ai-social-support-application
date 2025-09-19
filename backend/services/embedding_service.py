import asyncio
from typing import List, Dict, Any, Optional, Tuple
import hashlib
import json
from datetime import datetime
import logging

from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue
import numpy as np

from backend.config import settings

logger = logging.getLogger(__name__)

class EmbeddingService:
    """
    Vector embedding service for document content and semantic search
    Uses SentenceTransformers for encoding and Qdrant for vector storage
    """

    def __init__(self):
        # Initialize embedding model (CPU-friendly)
        self.model = SentenceTransformer(settings.embedding_model)
        self.embedding_dimension = settings.embedding_dimension

        # Initialize Qdrant client
        self.qdrant_client = QdrantClient(url=settings.qdrant_url)

        # Collection names for different types of content
        self.collections = {
            'documents': 'ai_social_documents',
            'applications': 'ai_social_applications',
            'eligibility_rules': 'ai_social_rules',
            'chat_history': 'ai_social_chats'
        }

        # Initialize collections
        asyncio.create_task(self._initialize_collections())

    async def _initialize_collections(self):
        """Initialize Qdrant collections if they don't exist"""
        try:
            for collection_name in self.collections.values():
                try:
                    self.qdrant_client.get_collection(collection_name)
                    logger.info(f"Collection {collection_name} already exists")
                except Exception:
                    # Collection doesn't exist, create it
                    self.qdrant_client.create_collection(
                        collection_name=collection_name,
                        vectors_config=VectorParams(
                            size=self.embedding_dimension,
                            distance=Distance.COSINE
                        )
                    )
                    logger.info(f"Created collection {collection_name}")

        except Exception as e:
            logger.error(f"Error initializing Qdrant collections: {str(e)}")

    def _generate_point_id(self, content: str, metadata: Dict[str, Any]) -> str:
        """Generate unique point ID based on content and metadata"""
        combined = f"{content}_{json.dumps(metadata, sort_keys=True)}"
        return hashlib.md5(combined.encode()).hexdigest()

    async def encode_text(self, text: str) -> List[float]:
        """Encode text into vector embedding"""
        try:
            # Run embedding in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            embedding = await loop.run_in_executor(
                None, self.model.encode, text
            )
            return embedding.tolist()
        except Exception as e:
            logger.error(f"Error encoding text: {str(e)}")
            return [0.0] * self.embedding_dimension

    async def encode_batch(self, texts: List[str]) -> List[List[float]]:
        """Encode multiple texts in batch for efficiency"""
        try:
            loop = asyncio.get_event_loop()
            embeddings = await loop.run_in_executor(
                None, self.model.encode, texts
            )
            return [emb.tolist() for emb in embeddings]
        except Exception as e:
            logger.error(f"Error encoding batch: {str(e)}")
            return [[0.0] * self.embedding_dimension] * len(texts)

    async def store_document_embeddings(
        self,
        application_id: int,
        document_id: int,
        content: str,
        document_type: str,
        extracted_data: Dict[str, Any]
    ) -> bool:
        """Store document content embeddings in Qdrant"""
        try:
            # Split content into chunks for better retrieval
            chunks = self._split_text_into_chunks(content)

            points = []
            for i, chunk in enumerate(chunks):
                if len(chunk.strip()) < 10:  # Skip very short chunks
                    continue

                embedding = await self.encode_text(chunk)
                point_id = self._generate_point_id(chunk, {
                    'application_id': application_id,
                    'document_id': document_id,
                    'chunk_index': i
                })

                point = PointStruct(
                    id=point_id,
                    vector=embedding,
                    payload={
                        'application_id': application_id,
                        'document_id': document_id,
                        'document_type': document_type,
                        'chunk_text': chunk,
                        'chunk_index': i,
                        'extracted_data': extracted_data,
                        'timestamp': datetime.now().isoformat(),
                        'content_type': 'document'
                    }
                )
                points.append(point)

            if points:
                self.qdrant_client.upsert(
                    collection_name=self.collections['documents'],
                    points=points
                )
                logger.info(f"Stored {len(points)} document chunks for doc {document_id}")
                return True

            return False

        except Exception as e:
            logger.error(f"Error storing document embeddings: {str(e)}")
            return False

    async def store_application_summary(
        self,
        application_id: int,
        summary_text: str,
        application_data: Dict[str, Any]
    ) -> bool:
        """Store application summary embedding"""
        try:
            embedding = await self.encode_text(summary_text)
            point_id = self._generate_point_id(summary_text, {'application_id': application_id})

            point = PointStruct(
                id=point_id,
                vector=embedding,
                payload={
                    'application_id': application_id,
                    'summary_text': summary_text,
                    'application_data': application_data,
                    'timestamp': datetime.now().isoformat(),
                    'content_type': 'application_summary'
                }
            )

            self.qdrant_client.upsert(
                collection_name=self.collections['applications'],
                points=[point]
            )

            logger.info(f"Stored application summary for app {application_id}")
            return True

        except Exception as e:
            logger.error(f"Error storing application summary: {str(e)}")
            return False

    async def store_eligibility_rules(self, rules: List[Dict[str, Any]]) -> bool:
        """Store eligibility rules for semantic matching"""
        try:
            points = []

            for rule in rules:
                rule_text = f"{rule.get('title', '')} {rule.get('description', '')} {rule.get('criteria', '')}"
                embedding = await self.encode_text(rule_text)
                point_id = self._generate_point_id(rule_text, rule)

                point = PointStruct(
                    id=point_id,
                    vector=embedding,
                    payload={
                        'rule_id': rule.get('id'),
                        'title': rule.get('title'),
                        'description': rule.get('description'),
                        'criteria': rule.get('criteria'),
                        'rule_type': rule.get('type'),
                        'rule_text': rule_text,
                        'timestamp': datetime.now().isoformat(),
                        'content_type': 'eligibility_rule'
                    }
                )
                points.append(point)

            if points:
                self.qdrant_client.upsert(
                    collection_name=self.collections['eligibility_rules'],
                    points=points
                )
                logger.info(f"Stored {len(points)} eligibility rules")
                return True

            return False

        except Exception as e:
            logger.error(f"Error storing eligibility rules: {str(e)}")
            return False

    async def search_similar_documents(
        self,
        query_text: str,
        application_id: Optional[int] = None,
        document_type: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Search for similar document content"""
        try:
            query_embedding = await self.encode_text(query_text)

            # Build filter conditions
            filter_conditions = []
            if application_id:
                filter_conditions.append(
                    FieldCondition(key="application_id", match=MatchValue(value=application_id))
                )
            if document_type:
                filter_conditions.append(
                    FieldCondition(key="document_type", match=MatchValue(value=document_type))
                )

            search_filter = Filter(must=filter_conditions) if filter_conditions else None

            results = self.qdrant_client.search(
                collection_name=self.collections['documents'],
                query_vector=query_embedding,
                query_filter=search_filter,
                limit=limit
            )

            return [
                {
                    'id': result.id,
                    'score': result.score,
                    'text': result.payload.get('chunk_text'),
                    'application_id': result.payload.get('application_id'),
                    'document_id': result.payload.get('document_id'),
                    'document_type': result.payload.get('document_type'),
                    'extracted_data': result.payload.get('extracted_data', {})
                }
                for result in results
            ]

        except Exception as e:
            logger.error(f"Error searching similar documents: {str(e)}")
            return []

    async def search_similar_applications(
        self,
        query_text: str,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Search for similar applications"""
        try:
            query_embedding = await self.encode_text(query_text)

            results = self.qdrant_client.search(
                collection_name=self.collections['applications'],
                query_vector=query_embedding,
                limit=limit
            )

            return [
                {
                    'id': result.id,
                    'score': result.score,
                    'application_id': result.payload.get('application_id'),
                    'summary_text': result.payload.get('summary_text'),
                    'application_data': result.payload.get('application_data', {})
                }
                for result in results
            ]

        except Exception as e:
            logger.error(f"Error searching similar applications: {str(e)}")
            return []

    async def find_relevant_rules(
        self,
        query_text: str,
        rule_type: Optional[str] = None,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Find relevant eligibility rules based on query"""
        try:
            query_embedding = await self.encode_text(query_text)

            filter_conditions = []
            if rule_type:
                filter_conditions.append(
                    FieldCondition(key="rule_type", match=MatchValue(value=rule_type))
                )

            search_filter = Filter(must=filter_conditions) if filter_conditions else None

            results = self.qdrant_client.search(
                collection_name=self.collections['eligibility_rules'],
                query_vector=query_embedding,
                query_filter=search_filter,
                limit=limit
            )

            return [
                {
                    'id': result.id,
                    'score': result.score,
                    'rule_id': result.payload.get('rule_id'),
                    'title': result.payload.get('title'),
                    'description': result.payload.get('description'),
                    'criteria': result.payload.get('criteria'),
                    'rule_type': result.payload.get('rule_type')
                }
                for result in results
            ]

        except Exception as e:
            logger.error(f"Error finding relevant rules: {str(e)}")
            return []

    async def store_chat_interaction(
        self,
        application_id: int,
        user_message: str,
        assistant_response: str,
        context: Dict[str, Any] = None
    ) -> bool:
        """Store chat interaction for context retrieval"""
        try:
            interaction_text = f"User: {user_message}\nAssistant: {assistant_response}"
            embedding = await self.encode_text(interaction_text)
            point_id = self._generate_point_id(interaction_text, {
                'application_id': application_id,
                'timestamp': datetime.now().isoformat()
            })

            point = PointStruct(
                id=point_id,
                vector=embedding,
                payload={
                    'application_id': application_id,
                    'user_message': user_message,
                    'assistant_response': assistant_response,
                    'context': context or {},
                    'timestamp': datetime.now().isoformat(),
                    'content_type': 'chat_interaction'
                }
            )

            self.qdrant_client.upsert(
                collection_name=self.collections['chat_history'],
                points=[point]
            )

            return True

        except Exception as e:
            logger.error(f"Error storing chat interaction: {str(e)}")
            return False

    def _split_text_into_chunks(self, text: str, chunk_size: int = 512, overlap: int = 50) -> List[str]:
        """Split text into overlapping chunks for better retrieval"""
        words = text.split()
        chunks = []

        for i in range(0, len(words), chunk_size - overlap):
            chunk = ' '.join(words[i:i + chunk_size])
            if len(chunk.strip()) > 10:  # Only include meaningful chunks
                chunks.append(chunk)

        return chunks

    async def get_collection_stats(self) -> Dict[str, Any]:
        """Get statistics about stored embeddings"""
        try:
            stats = {}
            for name, collection in self.collections.items():
                try:
                    info = self.qdrant_client.get_collection(collection)
                    stats[name] = {
                        'points_count': info.points_count,
                        'vectors_count': info.vectors_count,
                        'status': info.status
                    }
                except Exception:
                    stats[name] = {'status': 'not_found'}

            return stats

        except Exception as e:
            logger.error(f"Error getting collection stats: {str(e)}")
            return {}

    async def delete_application_data(self, application_id: int) -> bool:
        """Delete all embeddings related to an application"""
        try:
            for collection in self.collections.values():
                self.qdrant_client.delete(
                    collection_name=collection,
                    points_selector=Filter(
                        must=[
                            FieldCondition(
                                key="application_id",
                                match=MatchValue(value=application_id)
                            )
                        ]
                    )
                )

            logger.info(f"Deleted embeddings for application {application_id}")
            return True

        except Exception as e:
            logger.error(f"Error deleting application embeddings: {str(e)}")
            return False

# Singleton instance
embedding_service = EmbeddingService()