from python_reader import extract_text

# Step 1: Define the chunking function
def chunk_text(text, chunk_size, overlap):
    chunks = []
    for i in range(0, len(text), chunk_size-overlap):
        chunk = text[i:i + chunk_size]
        chunks.append(chunk)
    return chunks

# Step 2: Extract PDF text
pages_text = extract_text("data/Week 6 - Human Resources and Teamwork.pdf")

# Step 3: Store all chunks
all_chunks = []

for page_number, text in pages_text.items():
    page_chunks = chunk_text(text, 500, 100)

    for chunk in page_chunks:
        all_chunks.append({"page": page_number, "text": chunk})

# Step 4: Check results
print("Total chunks:", len(all_chunks))
print("First chunk:", all_chunks[0])