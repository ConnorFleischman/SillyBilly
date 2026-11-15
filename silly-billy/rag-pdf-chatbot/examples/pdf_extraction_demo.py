
import pymupdf

# Step 1: Open the PDF
doc = pymupdf.open("data/Week 6 - Human Resources and Teamwork.pdf")

# Step 2: Count the total pages
total_pages = doc.page_count
print(f"Total number of pages: {total_pages}")

# Step 3: Extract and store text from every page
pages_text = {
    page_number: page.get_text()
    for page_number, page in enumerate(doc, start=1)
}

# Step 4: Check how many pages were stored
print(f"Total pages stored: {len(pages_text)}")

# Step 5: Retrieve the text from page 10
print(pages_text[10])

# Step 6: Close the PDF
doc.close()
def extract_text(pdf_path):
    doc = pymupdf.open(pdf_path)
    pages_text = {}

    for page_number, page in enumerate(doc, start=1):
        pages_text[page_number] = page.get_text()

    doc.close()
    return pages_text
