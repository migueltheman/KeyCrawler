import requests
import hashlib
import os
import sys

from lxml import etree
from pathlib import Path
from dotenv import load_dotenv

from check import keybox_check as CheckValid

session = requests.Session()

# Load environment variables from .env file
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
cache_file = Path(__file__).resolve().parent / "cache.txt"

# Ensure the cache file exists
if not cache_file.exists():
    cache_file.touch()

cached_urls = set(open(cache_file, "r").readlines())

# Track if any changes were made
changes_made = False

# Function to fetch and print search results
def fetch_and_process_results(page):
    global changes_made
    print(f"Fetching results for page {page}...")  # Debug statement
    print(f"Fetching results for page {page}...", flush=True)  # Debug statement
    params = {"per_page": 100, "page": page}
    response = session.get(search_url, headers=headers, params=params)
    if response.status_code != 200:
        raise RuntimeError(f"Failed to retrieve search results: {response.status_code}")
    search_results = response.json()
    if "items" in search_results:
        for item in search_results["items"]:
            file_name = item["name"]
            # Process only XML files
            if file_name.lower().endswith(".xml"):
                raw_url: str = (
                    item["html_url"].replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
                )
                # Check if the file exists in cache
                if raw_url + "\n" in cached_urls:
                    continue
                else:
                    cached_urls.add(raw_url + "\n")
                # Fetch the file content
                file_content = fetch_file_content(raw_url)
                # Parse the XML
                try:
                    root = etree.fromstring(file_content)
                except etree.XMLSyntaxError:
                    print(f"Skipping invalid XML file: {raw_url}", flush=True)
                    continue
                # Get the canonical form (C14N)
                canonical_xml = etree.tostring(root, method="c14n")
                # Hash the canonical XML
                hash_value = hashlib.sha256(canonical_xml).hexdigest()
                file_name_save = save / (hash_value + ".xml")
                if not file_name_save.exists() and file_content and CheckValid(file_content):
                    print(f"New file found: {raw_url}", flush=True)
                    with open(file_name_save, "wb") as f:
                        f.write(file_content)
                    changes_made = True
    return len(search_results.get("items", [])) > 0  # Return True if there could be more results


# Function to fetch file content
def fetch_file_content(url: str):
    response = session.get(url)
    if response.status_code == 200:
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
        has_more = fetch_and_process_results(page)
        page += 1

    # Update cache
    with open(cache_file, "w") as f:
        f.writelines(cached_urls)

    for file_path in save.glob("*.xml"):
        file_content = file_path.read_text()  # Read file content as a string
        # Run CheckValid to determine if the file is still valid
        if not CheckValid(file_content):
            # Prompt user for deletion
            user_input = input(f"File '{file_path.name}' is no longer valid. Do you want to delete it? (y/N): ")
            if user_input.lower() == "y":
                try:
                    file_path.unlink()  # Delete the file
                    print(f"Deleted file: {file_path.name}", flush=True)
                    changes_made = True
                except OSError as e:
                    print(f"Error deleting file {file_path.name}: {e}", flush=True)
            else:
                print(f"Kept file: {file_path.name}", flush=True)

# Print message if no changes were made
if not changes_made:
    print("No new files or changes found.")