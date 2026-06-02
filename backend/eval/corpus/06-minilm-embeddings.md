# MiniLM embeddings

Embeddings are produced locally with the sentence-transformers model `all-MiniLM-L6-v2`, which
maps text to 384-dimensional vectors. Running the model locally keeps embedding free and private
— no text leaves the machine for embedding. Documents are embedded once at ingest time; at search
time only the query itself is embedded (a single short vector). The 384-dimension vectors are stored in a
pgvector column and indexed with HNSW for cosine similarity. Because pgvector dimensions are
fixed per column, the embedding model and its dimension are pinned; swapping models means a new
embeddings column and a re-embed, which is why the embedding table is kept separate from chunks.
