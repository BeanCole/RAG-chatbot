import json
from langchain_text_splitters import RecursiveCharacterTextSplitter

def transform_jsonl_to_chunks(input_file, output_file, chunk_size=500, chunk_overlap=50):
    """
    Transforms a JSONL file into chunks of text and saves them to an output file.

    Args:
        input_file (str): Path to the input JSONL file.
        output_file (str): Path to the output file where chunks will be saved.
        chunk_size (int): The maximum size of each chunk in characters.
        chunk_overlap (int): The number of overlapping characters between chunks.
    """
    # Initialize the text splitter
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)

    processed_trunks = set()  # To keep track of processed document IDs
    with open(input_file, 'r', encoding='utf-8') as infile:
        for line in infile:
            # Parse the JSON line
            doc = json.loads(line)
            # Assuming the text is stored under a key named 'content'
            content = doc.get('content', '')
            metadata = doc.get('metadata', {})
            doc_id = doc.get('doc_id', 'unknown_id')

            # Split the text into chunks
            chunks = text_splitter.split_text(content)

            # Write each chunk to the output file as a JSON line
            for i, chunk in enumerate(chunks):
                if metadata.get('type') == 'product_info':
                    enriched_text = f"[Thuộc sản phẩm id {doc_id}] {chunk}"
                else:
                    enriched_text = chunk
                chunk_doc = {
                    'parent_doc_id': doc_id,
                    'chunk_id': f'{doc_id}_chunk_{i}',
                    'content': enriched_text,
                    'metadata': metadata,
                }
                processed_trunks.add(json.dumps(chunk_doc, ensure_ascii=False))  # Store the chunk as a JSON string to avoid duplicates
    with open(output_file, 'w', encoding='utf-8') as outfile:
        for chunk in processed_trunks:
            outfile.write(chunk + '\n')
    print(f"Transformation complete. Output file: {output_file}")

if __name__ == "__main__":
    # Example usage
    input_file = '/app/data/products_data_raws.jsonl'  # Path to your input JSONL file
    output_file = '/app/data/products_data_chunks.jsonl'  # Path to your output file
    transform_jsonl_to_chunks(input_file, output_file)