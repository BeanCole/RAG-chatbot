import json
import uuid
import os
from openai import OpenAI
from qdrant_client import QdrantClient
from qdrant_client.http.models import PointStruct, VectorParams, Distance, PayloadSchemaType

embedding_model = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
qdrant_client = QdrantClient(
    url="http://qdrant_db:6333",
)

COLLECTION_NAME = "ecommerce_products"

def setup_qdrant():
    if not qdrant_client.collection_exists(COLLECTION_NAME):
        qdrant_client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=1536, distance=Distance.COSINE),
        )
        print(f"Collection '{COLLECTION_NAME}' created.")

        qdrant_client.create_payload_index(COLLECTION_NAME, "price", PayloadSchemaType.FLOAT)
        qdrant_client.create_payload_index(COLLECTION_NAME, "category", PayloadSchemaType.KEYWORD)
        print(f"Payload indexes for 'price' and 'category' created in collection '{COLLECTION_NAME}'.")

def embed_and_load_chunks(input_file: str, batch_size: int = 100):
    with open(input_file, 'r', encoding='utf-8') as f:
        points = []
        for line in f:
            doc = json.loads(line)
            content = doc.get('content', '')
            metadata = doc.get('metadata', {})
            parent_doc_id = doc.get('parent_doc_id', 'unknown_parent_id')
            chunk_id = doc.get('chunk_id', str(uuid.uuid4()))

            # Generate embedding for the chunk
            embedding_response = embedding_model.embeddings.create(
                model="text-embedding-3-small",
                input=content
            )
            embedding_vector = embedding_response.data[0].embedding

            # Create a PointStruct for Qdrant
            point = PointStruct(
                id=str(uuid.uuid5(uuid.NAMESPACE_URL, chunk_id)),
                vector=embedding_vector,
                payload={
                    "parent_doc_id": parent_doc_id,
                    "content": content,
                    "chunk_id": chunk_id,
                    "metadata": metadata
                }
            )
            points.append(point)

            # Insert points in batches
            if len(points) >= batch_size:
                qdrant_client.upsert(
                    collection_name=COLLECTION_NAME,
                    points=points
                )
                print(f"Inserted {len(points)} points into Qdrant collection '{COLLECTION_NAME}'.")
                points = []  # Clear the list for the next batch

        # Insert any remaining points
        if points:
            qdrant_client.upsert(
                collection_name=COLLECTION_NAME,
                points=points
            )
    print(f"Inserted {len(points)} points into Qdrant collection '{COLLECTION_NAME}'.")

if __name__ == "__main__":
    setup_qdrant()
    input_file = '/app/data/products_data_chunks.jsonl'
    print("Starting embedding and loading of chunks into Qdrant...")
    embed_and_load_chunks(input_file)
    print("Embedding and loading complete.")