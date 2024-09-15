import os
from unstructured_ingest.connector.local import SimpleLocalConfig
from unstructured_ingest.interfaces import (
    PartitionConfig,
    ProcessorConfig,
    ReadConfig,
)
from unstructured_ingest.runner import LocalRunner

from unstructured.staging.base import elements_from_json
from unstructured.chunking.title import chunk_by_title

from langchain.schema import Document
from qdrant_setup import qdrant_client

from qdrant_client import QdrantClient, models
from langchain_openai import OpenAIEmbeddings

from datetime import datetime

import uuid
import math
from dotenv import load_dotenv

# load API keys
load_dotenv()

def process_files(upload_directory, output_directory, qdrant_client, embedding_model, collection):
    # parse document and get json file (can comment out once json files are created)
    preprocess_documents(upload_directory, output_directory)
    
    # convert json data to chunks and then to langchain docs
    chunked_docs = process_chunks(output_directory)
    langchain_docs = chunks_to_docs(chunked_docs)
    
    # upload chunks to qdrant
    store_chunks(langchain_docs, embedding_model, qdrant_client, collection)

# ----- Helper Functions ----- #

def preprocess_documents(input_dir, output_dir): # doc_input_path, output_path
    """Chunks the documents in the input directory and outputs them as .json files.

    Args:
        input_dir: The directory which the original documents will be taken from
        output_dir: The directory which the json files containing the smaller chunks will be stored in.

    """
    try:
        clear_directory(output_dir)

        doc_input_path = "./" + input_dir
        output_path = "./" + output_dir

        runner = LocalRunner(
            processor_config=ProcessorConfig(
                verbose=True, # logs verbosity
                output_dir=output_path, # the local directory to store outputs
                num_processes=2,
            ),
            read_config=ReadConfig(),
            partition_config=PartitionConfig(
                partition_by_api=True,
                api_key=os.getenv("UNSTRUCTURED_API_KEY"),
            ),
            connector_config=SimpleLocalConfig(
                input_path=doc_input_path, # where local documents reside
                recursive=False, # whether to get the documents recursively from given directory
            ),
        )
        runner.run()

        print(f"Successfully processed documents.")
    except Exception as e:
        print(f"Error processing documents with Unstructured: {e}")

def clear_directory(directory_path):
    try:
        files = os.listdir(directory_path)
        for file in files:
            file_path = os.path.join(directory_path, file)
            if os.path.isfile(file_path):
                os.remove(file_path)

        print("All files deleted successfully.")
    except OSError:
        print("Error occurred while deleting files.")

def process_chunks(output_dir):

    """Combines smaller chunks to create larger, formatted chunks.

    Args:
        output_dir: The directory which the json files containing the smaller chunks are located.

    Returns:
        A list of chunked elements.
    """
    # import element types based on number of filetypes
    try:
        elements = []
        element_lists = []

        file = 0
        for filename in os.listdir(output_dir):
            filepath = os.path.join(output_dir, filename)
            elements = elements_from_json(filepath)

            # chunk elements
            chunked_elements = chunk_by_title(
                elements,
                max_characters=1000, # maximum for chunk size
                combine_text_under_n_chars=200, # combine chunks if too small
                multipage_sections=True,
            )

            elem = 0
            for element in chunked_elements:
                elem += 1
                print(f"File element {elem}: {element}\n\n")
            element_lists.append(chunked_elements)
            print(f"Document {file} chunked.")
            file += 1

        # flatten list
        elements = [
            element
            for e_list in element_lists
            for element in e_list
        ]

        # debugging!
        print("Chunked Elements: ")
        print([f"{element.text}\n" for element in elements])

        print("Successfully combined .json chunks!")
        return elements
    except Exception as e:
            print(f"Error chunking json files: {e}")

def chunks_to_docs(chunks):
    """Converts chunks created using Unstructured to Langchain Documents.

    Args:
        loaded_chunks: The list of chunks that will be converted to Langchain Documents.

    Returns:
        A list of Langchain Documents.
    """
    try:
        langchain_docs = []
        for chunk in chunks:
            doc = Document(
                page_content=chunk.text,  # The chunk's text content
                metadata=chunk.metadata.to_dict()
            )
            langchain_docs.append(doc)

        return langchain_docs
    except Exception as e:
        print(f"Error converting chunks to Langchain Documents: {e}")

def store_chunks(chunks: list[Document], embedding_model, qdrant_store, collection):
    """Transforms list of chunks to vectors and uploads them to the given qdrant vector store.

    Args:
        chunks: The list of chunks to be uploaded.
        embedding_model: The embedding model used to convert the chunks into vectors.
        qdrant_store: The qdrant store the vectors will be stored in.
    """
    current_timestamp = datetime.now().isoformat()

    # Index chunks into Qdrant
    points = []

    # divide large files across multiple point data buckets
    total_chunks = len(chunks)   
    max_set_size = 5
    totalSets = math.ceil(total_chunks/ max_set_size) # records the number of buckets used
    setCount = 1 # tracks the bucket lable of the current bucket 
    setSize = 0  # tracks the current size of the set

    for i, chunk in enumerate(chunks):
        print(f"Current File: {chunk.metadata['filename']}")
        setSize += 1

        # Extract content and metadata
        content = chunk.page_content
        metadata = chunk.metadata

        # add metadata to track where the file is and how many buckets are used
        metadata['set']  = setCount
        metadata['totalSets']  = totalSets
        
        # Add "date added" to metadata
        metadata['date_added'] = current_timestamp
        
        # Create vector for the chunk
        vector = embedding_model.embed_documents([content])[0]
        
        # Generate a unique UUID for each chunk
        chunk_id = str(uuid.uuid4())
        
        # Append point data
        points.append({
            "id": chunk_id,
            "vector": vector,
            "payload": {
                "content": content,
                "metadata": metadata
            }
        })

        print(f"SetSize: {setSize}")

        if setSize >= max_set_size:
            # Empty the points bucket because it is full
            qdrant_client.upsert(
                collection_name = collection,
                points = points
            )
            setCount += 1
            points = [] 
            setSize = 0  
            print(f"Uploaded and indexed {setSize} chunks")
    
    # Perform the upsert operation
    if len(points) > 0 :
        qdrant_store.upsert(
            collection_name = collection,
            points = points
    )
    
    print(f"Uploaded and indexed {len(chunks)} total chunks")

def delete_points_by_source_document(input_dir, collection, filename: str, qdrant_only=False, **kwargs: any) -> None:
    """Delete points from the collection associated with a specific source document, and delete that document from local storage.

    Args:
        input_dir: The directory the old non-json file is stored in.
        output_dir: The directory the old json file is stored in.
        collection: The collection that points will be deleted from.
        filename: The ID of the source document whose associated vectors should be deleted.
        qdrant_only: Whether to only delete the given file from the qdrant database or from the entire system.
    """
    try:
        if not qdrant_only:
            # # remove from local output folder     # preprocess clears jsons
            # json_file = filename + ".json"
            # output_path = os.path.join(output_dir, json_file)
            # os.remove(output_path)

            # remove from local upload folder
            upload_path = os.path.join(input_dir, filename)
            os.remove(upload_path)

        points_filter = models.Filter(
            must=[
                models.FieldCondition(
                    key="metadata.filename", 
                    match=models.MatchValue(value=filename),
                ),
            ],
        )

        qdrant_client.delete(
            collection_name=collection,
            points_selector=models.FilterSelector(filter=points_filter),
        )

        print("All points deleted successfully.")
    except Exception as e:
        print(f"Error removing points from qdrant: {e}")

if __name__ == "__main__":
#     upload_directory = "./uploads"
#     output_directory = "./local-ingest-output"
    
    input_dir = "uploads"
    output_dir = "output"

    # Initialize Qdrant client
    qdrant_client = QdrantClient(url='https://67be5618-eb3c-4be8-af45-490d7595393d.europe-west3-0.gcp.cloud.qdrant.io', 
        api_key=os.getenv("QDRANT_API_KEY"))

    # Initialize OpenAI Embeddings
    embedding_model = OpenAIEmbeddings(openai_api_key=os.getenv("OPENAI_API_KEY"))

    # to parse the documents and get the json file (can comment out once json files are created)
    # preprocess_documents(input_dir, output_dir)
    
    # to convert the json data to chunks and then to langchain docs
    chunked_docs = process_chunks(output_dir)
    langchain_docs = chunks_to_docs(chunked_docs)
    print("Langchain Docs: ")
    for i in range(len(langchain_docs)):
        print(f"Doc {i}: {langchain_docs[i]}\n\n")
    
    # to upload chunks to qdrant (must run with previous block of code)
    store_chunks(langchain_docs, embedding_model, qdrant_client, "test_collection")

    
