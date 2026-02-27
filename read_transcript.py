
"""
Read Transcript Module
Opens a Google Doc link from the spreadsheet and extracts the full meeting text.
"""


def read_doc(docs_service, doc_url):
    """
    Takes a Google Doc URL and returns the plain text content.
    Example URL: https://docs.google.com/document/d/1aeHxFjY.../edit
    """
    try:
        if not doc_url or "/d/" not in doc_url:
            return ""

        doc_id = doc_url.split("/d/")[1].split("/")[0]
        doc = docs_service.documents().get(documentId=doc_id).execute()

        content = ""
        for element in doc.get('body', {}).get('content', []):
            if 'paragraph' in element:
                for run in element['paragraph'].get('elements', []):
                    if 'textRun' in run:
                        content += run['textRun'].get('content', '')
        return content.strip()

    except Exception as e:
        print(f"[WARN] Could not read transcript: {e}")
        return ""
