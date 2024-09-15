from pathlib import Path
from shiny import App, ui, render, reactive
from search_engine import search_qdrant
import os
from qdrant_client import QdrantClient
from langchain_openai import OpenAIEmbeddings
from unstructured_processing import process_files, clear_directory, delete_points_by_source_document
from dotenv import load_dotenv


# UI Design
# css_file = Path(__file__).parent / "styles.css"

# load API keys
load_dotenv()

here = Path(__file__).parent

app_ui = ui.page_fillable(

    ui.include_css(here / "www/styles.css"),  # Include the custom CSS

    # Add CSS styling
    ui.tags.head(
      ui.tags.style(
        ui.HTML(
          "@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@100&display=swap')"
      )
      )
    ),

    # Top Bar
    ui.tags.div(
        ui.tags.div(
            # Info Circle Icon at the Start
            ui.input_action_button("info_circle", "",  # Empty label to show just the icon
                icon=ui.output_image("info_circle", width="30px", height="30px"),
                style="background: none; border: none; cursor: pointer; margin-left: 15px; padding: 0px; width: 30px; height: 30px; filter: invert(1);"  # Remove button styling
            ),
            # Social Media Icons at the End
            ui.tags.div(
                ui.tags.a(
                    ui.output_image("facebook_logo", width="30px", height="30px"),
                    href="https://www.facebook.com/positpbc/",
                    target="_blank",
                    style="color: white; margin-right: 15px; filter: invert(1);"
                ),
                ui.tags.a(
                    ui.output_image("linkedin_logo", width="30px", height="30px"),
                    href="https://www.linkedin.com/company/posit-software/",
                    target="_blank",
                    style="color: white; margin-right: 10px; filter: invert(1);"
                ),
                style="display: flex; justify-content: flex-end; padding: 10px;"  # Align icons to the right
            ),
            style="display: flex; justify-content: space-between; align-items: center;"
        ),
        class_="navbar-top"
    ),

    # Main Content
    ui.page_auto(
        ui.tags.div(
            ui.tags.div(
                ui.img(src="static/img/search_engine_logo_revised.svg", width="35%", height="auto"),  # Set width and height here
                style="padding-top: 60px; display: flex; justify-content: center; text-align: center;"  # Center the logo and add top padding
            ),
            style="position: relative;"
        ),
        ui.tags.div(
            ui.tags.div(
                ui.tags.span(
                    ui.img(src="static/img/search.svg", width="30px", height="30px"),
                    style="position: absolute; left: 10px; top: 50%; transform: translateY(-50%);"  # Position the icon correctly
                ),
                ui.tags.input(
                    type="text",
                    id="question_input",
                    placeholder="Please enter your question and press 'Search':",
                    style="width: 100%; padding-left: 50px; height: 50px; box-sizing: border-box;"  # Ensure text doesn't overlap with the icon
                ),
                style="position: relative; width: 100%; max-width: 800px; margin: 0 auto;"  # Relative position to contain the icon
            ),
            style="padding-top: 20px; position: relative; width: 100%; max-width: 800px; margin: 0 auto;"
        ),
        
        ui.tags.div(
            ui.div(
                ui.input_action_button("send_button", "Search", class_="btn-primary"),
                ui.input_action_button("upload", "Upload", class_="btn-primary"),
                ui.input_action_button("tools_button", "",  # Gear button for tools
                    icon=ui.tags.img(src="static/img/gear.svg", class_="gear-icon"),  # Use ui.tags.img with class
                    style="background: none; border: none; cursor: pointer; padding: 0;"),
                style="display: flex; justify-content: center; gap: 10px;"
            ),
            style="margin-top: 20px;"
        ),

        # JavaScript to trigger search on Enter key press
        ui.tags.script(
            """
            document.getElementById('question_input').addEventListener('keypress', function(event) {
                if (event.key === 'Enter') {
                    event.preventDefault();  // Prevent the default form submission
                    let query = document.getElementById('question_input').value.trim();
                    if (query !== "") {
                        document.getElementById('send_button').click();  // Programmatically click the Search button
                    }
                }
            });
            """
        ),
        ui.output_ui("search_results_section")
    )
)

# Initialize Qdrant client
qdrant_client = QdrantClient(url='https://67be5618-eb3c-4be8-af45-490d7595393d.europe-west3-0.gcp.cloud.qdrant.io', 
    api_key=os.getenv("QDRANT_API_KEY"))

# Initialize OpenAI Embeddings
embedding_model = OpenAIEmbeddings(openai_api_key=os.getenv("OPENAI_API_KEY"))

UPLOAD_DIR = "uploads"
OUTPUT_DIR = "output"
TEMP_DIR = "temp_uploads"

COLLECTION = "test_collection"

def create_directory(directory):
    if not os.path.exists(directory):
        os.makedirs(directory)

create_directory(UPLOAD_DIR)
create_directory(OUTPUT_DIR)
create_directory(TEMP_DIR)

def server(input, output, session):

    doc_types = reactive.Value(["PDF", "DOCX", "PPTX", "TXT"])
    sort_order = reactive.Value("Relevance")
    date_filter_enabled = reactive.Value(False)
    date_range_start = reactive.Value(None)
    date_range_end = reactive.Value(None)
    
    @reactive.Effect
    def update_settings():
        # Update document types
        if input.filter_doc_types():
            doc_types.set(input.filter_doc_types())
        else:
            doc_types.set([])

        # Update sort order
        if input.sort_order():
            sort_order.set(input.sort_order())
        else:
            sort_order.set("Relevance")

        # Update date filter state
        date_filter_enabled.set(input.enable_date_filter())

        # Update date range
        if date_filter_enabled():
            date_range_start.set(input.date_range()[0])
            date_range_end.set(input.date_range()[1])
        else:
            date_range_start.set(None)
            date_range_end.set(None)
    
    @render.image
    def gear_icon():
        img_path = here / "www/static/img/gear.svg"
        return {"src": str(img_path), "width": "30px", "height": "30px"}

    # Initialize a reactive value to store the selected sort order
    selected_sort_order = reactive.Value("Relevance")

    # Show modal when the gear icon button is clicked
    @reactive.effect
    @reactive.event(input.tools_button)
    def show_tools_modal():
        tools_modal = ui.modal(
            ui.h3("Search settings"),
            ui.tags.div(
                # Filter by Document Type
                ui.input_checkbox_group(
                    "filter_doc_types",
                    "Filter by Document Type:",
                    choices=["PDF", "DOCX", "PPTX", "TXT"],
                    selected=doc_types(),  # Use stored values
                    inline=True
                ),
                
                # Sort By Option
                ui.input_radio_buttons(
                    "sort_order",
                    "Sort By:",
                    choices=["Relevance", "Date Added"],
                    selected=sort_order(),  # Use stored values
                    inline=True
                ),
                
                # Enable Date Filtering Checkbox and Date Range Input
                ui.input_checkbox(
                    "enable_date_filter",
                    "Enable Date Filter:",
                    value=date_filter_enabled()  # Use stored value
                ),
                
                ui.input_date_range(
                    "date_range",
                    "Select Date Range:",
                    start=date_range_start(),  # Use stored value
                    end=date_range_end(),      # Use stored value
                    format='yyyy-mm-dd',
                    width="100%"
                ),
                
                class_="tools-modal"  # Apply CSS class to the whole modal
            ),
            easy_close=True,
            footer=None
        )
        ui.modal_show(tools_modal)

    # Save the current sort order selection when the modal is closed
    @reactive.effect
    def save_sort_order():
        sort_order = input.sort_order()
        if sort_order:
            selected_sort_order.set(sort_order)

    # Handle search queries when 'send_button' is clicked
    @output
    @render.ui
    @reactive.event(input.send_button)
    def query_results():
        query = input.question_input().strip()

        # Use reactive values instead of input for settings from the modal
        current_sort_order = sort_order()
        enable_date_filter = date_filter_enabled()
        start_date = date_range_start()
        end_date = date_range_end()

        current_doc_types = doc_types()

        if query:
            collection_name = COLLECTION
            results = search_qdrant(query, collection_name, sort_order=current_sort_order, start_date=start_date, end_date=end_date, enable_date_filter=enable_date_filter, selected_doc_types=current_doc_types)

            # Format and return results
            if results:
                # Wrap each result in a div with the search-result class
                result_texts = results  # Results should be a list of summary strings
                return ui.div([ui.div(ui.markdown(res), class_="search-result") for res in result_texts])
            else:
                return "No information found in the knowledge base."
        else:
            return "Please enter a query."

    @render.image
    def search_icon():
        img_path = here / "www/static/img/search.svg"
        return {"src": str(img_path), "width": "30px", "height": "30px"}
    @render.image
    def linkedin_logo():
        img_path = here / "www/static/img/linkedin.svg"
        return {"src": str(img_path), "width": "30px", "height": "30px"}

    @render.image
    def facebook_logo():
        img_path = here / "www/static/img/facebook.svg"
        return {"src": str(img_path), "width": "30px", "height": "30px"}
    @render.image
    def info_circle():
        img_path = here / "www/static/img/info-circle.svg"
        return {"src": str(img_path), "width": "30px", "height": "30px", "color": "white"}

    
    # Display a modal for document upload when the 'upload' button is clicked
    @reactive.effect
    @reactive.event(input.upload)
    def show_upload_modal():
        upload_modal = ui.modal(
            ui.input_file(
                # change
                "doc_upload", "Choose documents to upload", multiple=True, accept=[".pdf", ".docx", ".pptx", ".xlsx"]
            ),
            ui.input_action_button("upload_button", "Upload", class_="btn-primary"),
            easy_close=True,
            footer=None,
        )
        ui.modal_show(upload_modal)
    
    def show_upload_complete_modal():
        upload_complete_modal = ui.modal(
            "Upload complete!",
            easy_close=True,
            footer=None,
        )
        ui.modal_show(upload_complete_modal)

    # Handle document uploads when 'upload_button' is clicked
    @reactive.effect
    @reactive.event(input.upload_button)
    def handle_upload():
        print("entered handle_upload function")
        files = input.doc_upload()
        print("uploaded files")
        if files is not None:
            # uploaded_files = []
            for file_info in files:
                input_path = os.path.join("uploads", file_info["name"])
                temp_path = os.path.join(TEMP_DIR, file_info["name"])

                if os.path.exists(input_path):
                    show_duplicate_modal(input_path, temp_path, file_info)
                else:
                    upload_helper(input_path, temp_path, file_info)
        else:
            ui.modal_remove()  # Hide the modal after upload
    
    # function to either cancel or continue with the upload after duplicate files are detected
    def show_duplicate_modal(input_path, temp_path, file_info):
        print("entered display_modal")
        
        # create duplicate file modal for when duplicate files are detected
        duplicate_file_modal = ui.modal(
            ui.div(
                "A file of the same name has already been uploaded. Uploading again will overwrite the previous file's contents. Proceed with the upload?"
                ),
            ui.tags.div(
                ui.div(
                ui.input_action_button("cancel_duplicate", "Cancel"),
                ui.input_action_button("upload_duplicate", "Yes", class_="btn-primary")
                ),
                style="margin-top: 30px"
            ),
            title="Warning: duplicate file",
            easy_close=False,
            footer=None,
        )
        ui.modal_show(duplicate_file_modal)

        @reactive.effect  
        @reactive.event(input.cancel_duplicate)  
        def handle_cancel():  
            print("clicked cancel")
            ui.modal_remove()
        
        @reactive.effect  
        @reactive.event(input.upload_duplicate)  
        def handle_upload():  
            print("clicked upload")
            delete_points_by_source_document(UPLOAD_DIR, COLLECTION, file_info["name"])
            upload_helper(input_path, temp_path, file_info)

    def upload_helper(input_path, temp_path, file_info):
        print("entered upload helper")
        # Read and write file data
        with open(file_info["datapath"], "rb") as f:
            file_data = f.read()
        
        with open(input_path, "wb") as f1, open(temp_path, 'wb') as f2:
            f1.write(file_data)
            f2.write(file_data)
        
        # uploaded_files.append(file_info["name"])
        
        # Process the uploaded file
        process_files(TEMP_DIR, OUTPUT_DIR, qdrant_client, embedding_model, COLLECTION)

        # clear temporary directory
        clear_directory(TEMP_DIR)

        ui.modal_remove()  # Hide the modal after upload
        show_upload_complete_modal()


    # Handle search queries when 'send_button' is clicked
    @render.ui
    @reactive.event(input.send_button)
    def search_results_section():
        return ui.TagList(
            ui.hr(),
            ui.h3("Search Results", style="text-align: center;"),
            ui.output_ui("query_results")
        )
    
    @output
    @render.text
    def upload_status():
        return ""
    
    # Define the modal to show project information
    @reactive.effect
    @reactive.event(input.info_circle)
    def show_info_modal():
        info_modal = ui.modal(
            ui.h3("About This Project"),
            ui.p("This project demonstrates a RAG (Retrieval-Augmented Generation) AI-powered search engine. It allows users to search through uploaded documents and retrieve the most relevant information."),
            ui.input_action_button("close_modal", "Close", class_="btn-secondary"),
            easy_close=True,
            footer=None,
        )
        ui.modal_show(info_modal)

    # Define the event to close the modal
    @reactive.effect
    @reactive.event(input.close_modal)
    def close_modal():
        ui.modal_remove()

www_dir = Path(__file__).parent / "www"
app = App(app_ui, server, static_assets=www_dir)

if __name__ == "__main__":
    app.run()
