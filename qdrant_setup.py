from qdrant_client import QdrantClient, models
import os
from dotenv import load_dotenv

# load API keys
load_dotenv()

# Initialize Qdrant client
qdrant_client = QdrantClient(
    url='https://67be5618-eb3c-4be8-af45-490d7595393d.europe-west3-0.gcp.cloud.qdrant.io', 
    api_key=os.getenv("QDRANT_API_KEY"))  # Adjust URL as needed

# Define the collection name
collection_name = "test_collection"

def setup_qdrant_collection():
    try:
        # Check if the collection exists
        collections = qdrant_client.get_collections()
        existing_collections = [c.name for c in collections.collections]
        
        if collection_name not in existing_collections:
            # Create the collection if it doesn't exist
            qdrant_client.create_collection(
                collection_name=collection_name,
                vectors_config=models.VectorParams(
                    size=1536,  # Adjust size based on the embedding model
                    distance=models.Distance.COSINE
                )
            )
            print(f"Collection '{collection_name}' created.")
        else:
            print(f"Collection '{collection_name}' already exists.")
    except Exception as e:
        print(f"Error setting up Qdrant collection: {e}")

def clear_qdrant_collection():
    try:
        # Delete the collection if it exists
        qdrant_client.delete_collection(collection_name=collection_name)
        print(f"Collection '{collection_name}' deleted.")
    except Exception as e:
        print(f"Error clearing Qdrant collection: {e}")

if __name__ == "__main__":
    # Clear and set up the collection
    clear_qdrant_collection()
    setup_qdrant_collection()
