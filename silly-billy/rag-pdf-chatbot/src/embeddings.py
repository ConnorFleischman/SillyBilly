from sentence_transformers import SentenceTransformer

# Load the embedding model
model = SentenceTransformer("all-MiniLM-L6-v2")


# Function to generate an embedding for input text
def get_embedding(text):
    return model.encode(text)