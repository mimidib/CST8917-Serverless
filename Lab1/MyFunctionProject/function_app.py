# =============================================================================
# IMPORTS - Libraries we need for our function
# =============================================================================
import azure.functions as func  # Azure Functions SDK - required for all Azure Functions
import logging                  # Built-in Python library for printing log messages
import json                     # Built-in Python library for working with JSON data
import re                       # Built-in Python library for Regular Expressions (pattern matching)
from datetime import datetime, timezone   # Built-in Python library for working with dates and times
from azure.cosmos import CosmosClient, exceptions, PartitionKey # Azure Cosmos DB SDK - for connecting to our database 
import os # Built-in python library for getting our env variables
import uuid # Built-in python library for generating unique identifiers

# =============================================================================
# CREATE THE FUNCTION APP
# =============================================================================
# This creates our Function App with anonymous access (no authentication required)
# Think of this as the "container" that holds all our functions
app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)


# Create Cosmos DB Client - doens't connect here, just stores the client object in memory for use later
DATABASE_CONNECTION_STRING = os.environ.get("DATABASE_CONNECTION_STRING") # Lazy, no connectoin - using environ.get returns None if missing so it doesn't take dow nthe whole app and therefore every endpoint. Graceful degredation if CosmosDB isn't working or connection string is missing 
cosmos_client = CosmosClient.from_connection_string(DATABASE_CONNECTION_STRING) # lazy 

database = cosmos_client.get_database_client("TextAnalyzerDB") # lazy 
container = database.get_container_client("analyses") # lazy 


# =============================================================================
# DEFINE THE TEXT ANALYZER FUNCTION
# =============================================================================
# The @app.route decorator tells Azure: "When someone visits /api/TextAnalyzer, run this function"
# This is called a "decorator" - it adds extra behavior to our function
@app.route(route="TextAnalyzer")
def TextAnalyzer(req: func.HttpRequest) -> func.HttpResponse:
    """
    This function analyzes text and returns statistics about it.

    Parameters:
        req: The incoming HTTP request (contains the text to analyze)

    Returns:
        func.HttpResponse: JSON response with analysis results
    """

    # Log a message so we can see in Azure Portal when the function is called
    logging.info('Text Analyzer API was called!')

    # =========================================================================
    # STEP 1: GET THE TEXT INPUT
    # =========================================================================

    # refactor to use helper function
    text = _extract_text(req) # handles if text is empty in both url and json

    # =========================================================================
    # STEP 2: HANDLE MISSING TEXT (Error Response) - refactored for Gaurd clause
    # =========================================================================
    if not text:
        
        # If no text was provided, return helpful instructions
        instructions = {
            "error": "No text provided",
            "howToUse": {
                "option1": "Add ?text=YourText to the URL",
                "option2": "Send a POST request with JSON body: {\"text\": \"Your text here\"}",
                "example": "https://your-function-url/api/TextAnalyzer?text=Hello world"
            }
        }

        # Return an error response
        # status_code=400 means "Bad Request - client made an error"
        return func.HttpResponse(
            json.dumps(instructions, indent=2),
            mimetype="application/json",
            status_code=400
        )
    # =========================================================================
    # STEP 3: ANALYZE THE TEXT (if text was provided)
    # =========================================================================
    else:
        # ----- Word Analysis -----
        # split() breaks the text into a list of words
        # "Hello world" becomes ["Hello", "world"]
        words = text.split()

        # len() counts items in a list
        # ["Hello", "world"] has length 2
        word_count = len(words)

        # ----- Character Analysis -----
        # len() on a string counts characters (including spaces)
        # "Hello world" has 11 characters
        char_count = len(text)

        # replace(" ", "") removes all spaces, then we count
        # "Hello world" becomes "Helloworld" (10 characters)
        char_count_no_spaces = len(text.replace(" ", ""))

        # ----- Sentence Analysis -----
        # re.findall() finds all matches of a pattern
        # r'[.!?]+' means: find any sequence of periods, exclamation marks, or question marks
        # "Hello! How are you?" returns ['!', '?'] (2 sentences)
        # The "or 1" means: if no punctuation found, assume at least 1 sentence
        sentence_count = len(re.findall(r'[.!?]+', text)) or 1

        # ----- Paragraph Analysis -----
        # Paragraphs are separated by blank lines (two newlines: \n\n)
        # split('\n\n') breaks text at blank lines
        # We filter out empty paragraphs with "if p.strip()"
        # strip() removes whitespace - empty strings become "" which is False
        paragraph_count = len([p for p in text.split('\n\n') if p.strip()])

        # ----- Reading Time Calculation -----
        # Average reading speed is about 200 words per minute
        # round(x, 1) rounds to 1 decimal place
        # 100 words / 200 wpm = 0.5 minutes
        reading_time_minutes = round(word_count / 200, 1)

        # ----- Average Word Length -----
        # Total characters (no spaces) divided by number of words
        # We check "if word_count > 0" to avoid dividing by zero
        avg_word_length = round(char_count_no_spaces / word_count, 1) if word_count > 0 else 0

        # ----- Find Longest Word -----
        # max() finds the largest item
        # key=len means "compare words by their length"
        # max(["Hi", "Hello", "Hey"], key=len) returns "Hello"
        longest_word = max(words, key=len) if words else ""

        # =====================================================================
        # STEP 4: BUILD THE RESPONSE
        # =====================================================================
        # Create a Python dictionary with all our analysis results
        # This will be converted to JSON format
        response_data = {
            "id": str(uuid.uuid4()), #the unique ID used for this analysis also used as the partition id for Cosmos DB partition storing
            "analysis": {
                "wordCount": word_count,
                "characterCount": char_count,
                "characterCountNoSpaces": char_count_no_spaces,
                "sentenceCount": sentence_count,
                "paragraphCount": paragraph_count,
                "averageWordLength": avg_word_length,
                "longestWord": longest_word,
                "readingTimeMinutes": reading_time_minutes
            },
            "metadata": {
                # datetime.now() gets current time, isoformat() converts to string
                # Example: "2024-01-15T14:30:00.000000"
                "analyzedAt": datetime.now(timezone.utc).isoformat(),

                # Show first 100 characters of text as a preview
                # The syntax: value_if_true if condition else value_if_false
                # This is called a "ternary operator" or "conditional expression"
                "textPreview": text[:100] + "..." if len(text) > 100 else text
            },
            "originalText": text
        }

        # =====================================================================
        # STEP 5: CREATE AN ITEM IN COSMOS DB
        # =====================================================================
        # Creating an item vs replacing as these records will always be new analyses, not updates to old ones 
        try:
            container.create_item(response_data)
        except exceptions.CosmosHttpResponseError as e:
            logging.error(f"Error saving to Cosmos DB: {e.message}")
            return func.HttpResponse("Database error", status_code=500)
        
        # =====================================================================
        # STEP 6: STORE ANALYSIS IN COSMOS DB
        # =====================================================================

        # =====================================================================
        # STEP 7: CREATE RESPONSE & RETURN
        # =====================================================================
        # Return a successful HTTP response
        # json.dumps() converts Python dictionary to JSON string
        # indent=2 makes the JSON nicely formatted (2 spaces per indent level)
        # mimetype tells the browser "this is JSON data"
        # status_code=200 means "OK - Success"
        return func.HttpResponse(
            json.dumps(response_data, indent=2),
            mimetype="application/json",
            status_code=200
        )

# helper funciton to handle if text is empty in both url and json
def _extract_text(req:func.HttpRequest) -> str | None:
    # First, try to get 'text' from the URL query string
    # Example URL: /api/TextAnalyzer?text=Hello world
    # req.params.get('text') would return "Hello world"
    text = req.params.get('text') 

    # If text wasn't in the URL, try to get it from the request body (JSON)
    if text is None: 
        try:
            body = req.get_json()
        except ValueError:
            logging.warning("Request body is not valid JSON")
            return None
        # return Json body if body.get("text") exists and body is a dict, otherwise return None
        return body.get("text") if isinstance(body, dict) else None
    else: # return the URL value if text exists
        return text

# Retrieve the history of analysis
@app.route(route="GetAnalysisHistory")
def GetAnalysisHistory(req: func.HttpRequest) -> func.HttpResponse:
    """
    This function retrieves the history of text analyses from Cosmos DB.

    Parameters:
        req: The incoming HTTP request (not used in this function)
    Returns:
        func.HttpResponse: JSON response with list of past analyses
    """