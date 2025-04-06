import requests
import hashlib
import os
import sys
import traceback  # Import the traceback module

from lxml import etree
from pathlib import Path
from dotenv import load_dotenv

from check import keybox_check as CheckValid

session = requests.Session()

# Load environment variables from .env file
print("Loading environment variables...", flush=True)
load_dotenv()
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

if not GITHUB_TOKEN:
    raise ValueError("GITHUB_TOKEN is not set in the .env file")

# Search query
search_query = "<AndroidAttestation>"
search_url = f"https://api.github.com/search/code?q={search_query}"

# Headers for the API request
headers = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json",
}

save = Path(__file__).resolve().parent / "keys"
print(f"Save directory: {save}", flush=True)
cache_file = Path(__file__).resolve().parent / "cache.txt"
print(f"Cache file: {cache_file}", flush=True)

# Ensure the cache file exists
print("Ensuring cache file exists...", flush=True)
if not cache_file.exists():
    print("Cache file does not exist, creating...", flush=True)
    cache_file.touch()
else:
    print("Cache file exists.", flush=True)

print("Reading cached URLs...", flush=True)
cached_urls = set(open(cache_file, "r").readlines())
print(f"Number of cached URLs: {len(cached_urls)}", flush=True)

# Track if any changes were made
changes_made = False
print(f"Initial changes_made: {changes_made}", flush=True)

# Function to fetch and print search results
def fetch_and_process_results(page):
    global changes_made
    print(f"Fetching results for page {page}...", flush=True)  # Debug statement
    params = {"per_page": 100, "page": page}
    print(f"Request parameters: {params}", flush=True)
    response = session.get(search_url, headers=headers, params=params)
    print(f"Response status code: {response.status_code}", flush=True)
    if response.status_code != 200:
        raise RuntimeError(f"Failed to retrieve search results: {response.status_code}")
    search_results = response.json()
    if "items" in search_results:
        print(f"Number of items in search results: {len(search_results['items'])}", flush=True)
        for item in search_results["items"]:
            file_name = item["name"]
            print(f"Processing item: {file_name}", flush=True)
            # Process only XML files
            if file_name.lower().endswith(".xml"):
                raw_url: str = (
                    item["html_url"].replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
                )
                print(f"Raw URL: {raw_url}", flush=True)
                # Check if the file exists in cache
                if raw_url + "\n" in cached_urls:
                    print("File found in cache, skipping...", flush=True)
                    continue
                else:
                    print("File not found in cache, adding to cache...", flush=True)
                    cached_urls.add(raw_url + "\n")
                # Fetch the file content
                file_content = fetch_file_content(raw_url)
                # Parse the XML
                try:
                    print("Parsing XML...", flush=True)
                    root = etree.fromstring(file_content)
                    print("XML parsed successfully.", flush=True)
                except etree.XMLSyntaxError:
                    print(f"Skipping invalid XML file: {raw_url}", flush=True)
                    continue
                # Get the canonical form (C14N)
                print("Getting canonical XML...", flush=True)
                canonical_xml = etree.tostring(root, method="c14n")
                # Hash the canonical XML
                print("Hashing canonical XML...", flush=True)
                hash_value = hashlib.sha256(canonical_xml).hexdigest()
                file_name_save = save / (hash_value + ".xml")
                print(f"File save path: {file_name_save}", flush=True)
                if not file_name_save.exists() and file_content and CheckValid(file_content):
                    print(f"New file found: {raw_url}", flush=True)
                    with open(file_name_save, "wb") as f:
                        f.write(file_content)
                    changes_made = True
                    print(f"changes_made set to: {changes_made}", flush=True)
    has_more = len(search_results.get("items", [])) > 0
    print(f"has_more: {has_more}", flush=True)
    return has_more  # Return True if there could be more results


# Function to fetch file content
def fetch_file_content(url: str):
    print(f"Fetching file content from {url}...", flush=True)  # Debug statement
    response = session.get(url)
    print(f"Response status code: {response.status_code}", flush=True)
    if response.status_code == 200:
        print("File content fetched successfully.", flush=True)
        return response.content
    else:
        raise RuntimeError(f"Failed to download {url}")


# Main logic
try:
    print("Starting the crawling process...", flush=True)
    # Fetch all pages
    page = 1
    has_more = True
    while has_more:
        print(f"Starting page {page}...", flush=True)
        has_more = fetch_and_process_results(page)
        page += 1
        print(f"Completed page {page-1}. has_more: {has_more}", flush=True)

    # Update cache
    print("Updating cache file...", flush=True)
    with open(cache_file, "w") as f:
        f.writelines(cached_urls)
    print("Cache file updated.", flush=True)

    print("Checking for invalid files...", flush=True)
    for file_path in save.glob("*.xml"):
        print(f"Checking file: {file_path}", flush=True)
        file_content = file_path.read_text()  # Read file content as a string
        # Run CheckValid to determine if the file is still valid
        if not CheckValid(file_content):
            # Prompt user for deletion
            print(f"File {file_path.name} is no longer valid.", flush=True)
            user_input = input(f"File '{file_path.name}' is no longer valid. Do you want to delete it? (y/N): ")
            if user_input.lower() == "y":
                try:
                    file_path.unlink()  # Delete the file
                    print(f"Deleted file: {file_path.name}", flush=True)
                    changes_made = True
                    print(f"changes_made set to: {changes_made}", flush=True)
                except OSError as e:
                    print(f"Error deleting file {file_path.name}: {e}", flush=True)
            else:
                print(f"Kept file: {file_path.name}", flush=True)
        else:
            print(f"File {file_path.name} is still valid.", flush=True)

    # Print message if no changes were made
    print("Checking if changes were made...", flush=True)
    if not changes_made:
        print("No changes were made to the files.", flush=True)
    else:
        print("Changes were made.", flush=True)

except Exception as e:
    print(f"An error occurred: {e}", file=sys.stderr, flush=True)
    traceback.print_exc(file=sys.stderr)  # Print the exception traceback to stderr