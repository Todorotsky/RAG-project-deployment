import os
import openai
from qdrant_client import QdrantClient, models
from langchain_openai import OpenAIEmbeddings
from datetime import datetime
from dotenv import load_dotenv

# load API keys
load_dotenv()

# Initialize Qdrant client
qdrant_client = QdrantClient(url='https://67be5618-eb3c-4be8-af45-490d7595393d.europe-west3-0.gcp.cloud.qdrant.io', 
    api_key=os.getenv("QDRANT_API_KEY"))  # Adjust URL as needed

# Initialize OpenAI Embeddings
embedding_model = OpenAIEmbeddings(openai_api_key=os.getenv("OPENAI_API_KEY"))

mime_type_mapping = {
    "application/pdf": "PDF",
    "application/msword": "DOC",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "DOCX",
    "application/vnd.ms-excel": "XLS",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "XLSX",
    "application/vnd.ms-powerpoint": "PPT",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": "PPTX",
    "text/plain": "TXT",
    "text/csv": "CSV",
    "image/jpeg": "JPG",
    "image/png": "PNG",
    "image/gif": "GIF",
    "application/zip": "ZIP",
}

def search_qdrant(query: str, collection_name: str, top_k: int = 15, min_score: float = 0.8, sort_order="Relevance", start_date=None, end_date=None, enable_date_filter=False, selected_doc_types=None):
    # Generate embedding for the query
    query_embedding = embedding_model.embed_documents([query])[0]
    print(f"Query embedding: {query_embedding}")

    # Prepare filter conditions based on date range and document type
    must_conditions = []

    # Filter by date if enabled
    if enable_date_filter:
        datetime_range = models.DatetimeRange()

        if start_date:
            start_date_rfc3339 = start_date.isoformat() + "T00:00:00"
            datetime_range.gte = start_date_rfc3339

        if end_date:
            end_date_rfc3339 = end_date.isoformat() + "T23:59:59"
            datetime_range.lte = end_date_rfc3339

        if datetime_range.gte or datetime_range.lte:
            must_conditions.append(
                models.FieldCondition(
                    key="metadata.date_added",
                    range=datetime_range
                )
            )

    # Filter by document type
    if selected_doc_types:
        doc_type_conditions = []
        for mime, doc_type in mime_type_mapping.items():
            if doc_type in selected_doc_types:
                doc_type_conditions.append(mime)

        if doc_type_conditions:
            must_conditions.append(
                models.FieldCondition(
                    key="metadata.filetype",
                    match=models.MatchAny(any=doc_type_conditions)
                )
            )

    # Debug: Check if conditions are correctly added
    print(f"Filter conditions: {must_conditions}")

    # Construct the filter if there are any conditions
    filter_condition = models.Filter(must=must_conditions) if must_conditions else None

    # Perform search in Qdrant with filters
    results = qdrant_client.search(
        collection_name=collection_name,
        query_vector=query_embedding,
        limit=top_k,
        search_params=models.SearchParams(hnsw_ef=128, exact=False),
        query_filter=filter_condition  # Correctly pass the filter to the search function
    )
    
    # Debug: Print raw search results
    print("Raw search results:", results)

    # Process results to avoid duplicates and summarize
    unique_sources = {}
    chunks_by_doc = {}

    for result in results:
        print(f"Processing result: ID={result.id}, Score={result.score}")
        if result.score < min_score:
            continue

        # Retrieve the document using the ID
        retrieve_result = qdrant_client.retrieve(
            collection_name=collection_name,
            ids=[result.id]
        )
        
        # Debug: Print the retrieved result
        print("Retrieve result:", retrieve_result)

        if retrieve_result and isinstance(retrieve_result, list) and len(retrieve_result) > 0:
            payload = retrieve_result[0].payload
            content = payload.get("content", "")
            metadata = payload.get("metadata", {})
            source = metadata.get("filename", "")
            filetype = metadata.get("filetype", "")

            # Process the content and add to chunks_by_doc
            if source and content:
                print(f"Content: {content}\n")
                print(f"Source{source}\n\n")
                # for word... :(
                if not (filetype.endswith("pdf") or filetype.endswith("pptx")):
                    if source not in chunks_by_doc:
                        chunks_by_doc[source] = [{
                            'content': content,
                            'page_number': 'not available',
                        }]
                    else:
                        chunks_by_doc[source].append({
                            'content': content,
                            'page_number': 'not available',
                        })
                # for non-word
                else:
                    if source not in chunks_by_doc:
                        chunks_by_doc[source] = [{
                            'content': content,
                            'page_number': metadata['page_number'],
                        }]
                    else:
                        chunks_by_doc[source].append({
                            'content': content,
                            'page_number': metadata['page_number'],
                        })
                    
                # Only add to unique_sources if not already present
                if source not in unique_sources:
                    unique_sources[source] = {
                        'score': result.score,
                        'content': content,
                        'metadata': metadata
                    }
    for key in chunks_by_doc.keys():
        print(key)
        for chunk in chunks_by_doc[key]:
            print(f"Chunk: {chunk}")

    # Check if no results were found
    if not unique_sources:
        print("No information found in the knowledge base.")
        return ["No information found in the knowledge base."]

    # Create summaries with hyperlinks
    final_results = []

    for source, data in unique_sources.items():
        chunks = []
        for chunk in chunks_by_doc[source]:
            chunks.append(chunk)
        summary = get_openai_summary(query, chunks)
        # Ensure summary is a string
        summary_str = summary if isinstance(summary, str) else str(summary)
        # Extract the file type from the metadata
        file_type = data['metadata'].get('filetype', '')

        # Extract the file type display name using the mapping
        file_type_display = mime_type_mapping.get(file_type, file_type.split('/')[-1].upper())
    
        # Format result text with Source, Summary, Content, and Score

        # Extract and format the "date added"
        date_added = data['metadata'].get('date_added', '')
        if date_added:
            try:
                date_obj = datetime.fromisoformat(date_added)
                formatted_date = date_obj.strftime('%b %d, %Y')
            except ValueError:
                formatted_date = '<b>Content Extract: </b>'
            date_class = "date-added"  # Class for styled date
        else:
            formatted_date = '<b>Content Extract: </b>'
            date_class = "date-not-available"  # Class for non-styled date
        
        content_preview = data['content']
        if len(content_preview) > 200:
            truncated_content = content_preview[:200].rsplit(' ', 1)[0]  # Truncate to the last complete word within 200 characters
            content_preview = truncated_content + '...'
        
        # Extract and format the "page number"
        page_numbers = set()
        for chunk in chunks_by_doc[source]:
            if chunk['page_number']:
                page_numbers.add(chunk['page_number'])
            
        if not page_numbers:
            page_numbers = "not available"


        result_text = (f"<b>Source:</b> {source}, <span class='{date_class}'>{formatted_date}</span><br>"
                    #   <a href={source}>{source}</a>
                       f"<b>Page(s):</b> {page_numbers}<br><br>"
                    #    f"<span class='{date_class}'>{formatted_date}</span>"
                    #    f"<span class='content-preview'>{content_preview}</span><br><br>"
                       f"<b>Summary:</b> {summary_str} <br><br>"
                       f"<b>Similarity Score: {round(data['score'], 3)}</b>"
                       f"<span class='filetype-label'>{file_type_display}</span>"
                       )
        final_results.append(result_text)

    return final_results



from openai import OpenAI

client = OpenAI(
    api_key=os.environ.get("OPENAI_API_KEY"),
    )

def get_openai_summary(query, content):
    response = client.chat.completions.create(
        messages=[
            {"role": "system", "content": "You are an assistant whose goal is to help the user search for documents in your information database that are most relevant to the topic or question they ask you."},
            {"role": "user", "content": f"I will give you some excerpts from a document in the form of a list. Here is the user's query: {query}. Please respond to the query by providing a one to three sentence summary using information from the following content:\n\n{content}."}
        ],
        model="gpt-3.5-turbo",
        max_tokens=100
    )

    # Extract summary from the response
    summary = response.choices[0].message.content
    return summary

# search_qdrant("What activities does Athena Deng enjoy?", "test_collection")