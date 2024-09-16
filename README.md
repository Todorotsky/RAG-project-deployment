# RAG-project

This project demonstrates a Retrieval-Augmented Generation (RAG) AI-powered search engine. The Shiny application developed in this project allows users to upload various document types, which are then analyzed and indexed by an AI model. The app provides an intuitive search interface that leverages RAG to deliver precise and contextually relevant results.

## Key Prerequisites and Setup

If you are looking to create a new set of API keys for your use, please refer to steps 1-4, otherwise, go to step 5 for use of the default ones
1. Create an OpenAI API key using this url (https://platform.openai.com/api-keys). You need to have an account with OpenAI.
2. Request an Unstructured API key (For this PoC, we have tested this with the Unstructured Free API and not the Serverless API) (https://unstructured.io/api-key-free). Please note that currently, the usage with the free API is capped at 1000 words. You can opt for the serverless api if you want to scale it up for production.
3. Create a new account with QDrant cloud (https://cloud.qdrant.io/). Create a new QDrant cluster and a new QDrant API key.
4. Store the 3 API keys created in the .env file
5. Create a new virtual environment and load all the packages listed in requirements.txt
6. Run the app locally using the command
```
python -m app.py
```
(use app instead of app.py if you're running it on Windows)


7. Deploy the app on Shinyapps by running the following commands:

7.1. Install the packages shiny and rsconnect-python:
```
pip install shiny rsconnect-python
```
7.2. Create a new account on Shinyapps and store the account name, token and secret when you log in for the first time. Run the command by replacing the parameters with the actual values:
```
rsconnect add \
	  --account <ACCOUNT> \
	  --name <NAME> \
	  --token <TOKEN> \
	  --secret <SECRET>
```
7.3. Go to the working directory containing app.py and run the command to deploy the app:
```
rsconnect deploy shiny ./ --name <NAME> --title <TITLE>
```
Now, the app has been deployed to Shinyapps with a custom URL.

## Usage
1. Upload the documents to the document repository against which you would like to query:
![Upload In Progress](https://github.com/user-attachments/assets/140db502-910d-4000-bae0-4b71488b2f9f)

2. Set the relevant search and filter settings based on your preference. You can filter the results by document type (such as show only the pdf results), sort the documents by relevancy or date added, or only search across the documents which have been uploaded within a custom date range of your choice (Note: For the last one, the date filter checkbox must be enabled).
![Search Settings](https://github.com/user-attachments/assets/6435cb5f-92df-45f0-9cbb-fa2f7073e16c)

3. Search based on keyword or ask a question to receive a summarized response by document for the top relevant matches. The model also assigns a vector based similarity score for the top most relevant matches. Here are some sample examples:
![image](https://github.com/user-attachments/assets/b961775f-2df5-4ea6-b34e-7453351a6da2)
![image2](https://github.com/user-attachments/assets/3c1b4b64-e2ef-4e87-8930-6be5b13aa4cc)
![image4](https://github.com/user-attachments/assets/e32ee43b-8511-4f06-b0a5-e4bdd0ccf677)


## Key Features
1. Display the top document matches from the repository based on your user query and search settings across different document types (Note: Try out different query combinations. To get more relevant results, ensure that the query is specifc to what you are looking for).
2. Get summarized AI generated responses based on your query for the most relevant document matches.
3. Get the page numbers of the documents (if applicable) that are most likely to contain relevant information about your query
4. Display a AI generated similarity score between 0 and 1 (where 1 denotes the highest match) between the query and the document.

## Key Technologies Used
1. Langchain
2. OpenAI (for embeddings and document summarization) (For this project, we used GPT-3.5 turbo for document summaries based on the user query)
3. Unstructured (for document preprocessing)
4. QDrant (vector store to store document chunk embeddings)
5. Shiny (User Interface)

