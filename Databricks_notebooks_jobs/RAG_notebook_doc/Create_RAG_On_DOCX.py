# Databricks notebook source
# DBTITLE 1,Install libraries
# Create RAG on DOCX File
# This reads the .docx file and creates Vector Search for RAG

print("🧪 CREATING RAG ON DOCX FILE")
print("="*80)
print("\nThis will:")
print("  1. Read Pipeline_Complete_Documentation.docx")
print("  2. Extract and chunk text")
print("  3. Create Vector Search index")
print("  4. Test semantic search")
print("\n" + "="*80)

# Install required libraries
%pip install databricks-vectorsearch python-docx --quiet
dbutils.library.restartPython()

# COMMAND ----------

# DBTITLE 1,Read DOCX and extract text
from docx import Document
from pyspark.sql.functions import *
from pyspark.sql.types import *
from databricks.vector_search.client import VectorSearchClient

print("\n📝 Step 1: Reading DOCX file...\n")

# Read the DOCX file
docx_path = "/Workspace/Users/shivam.singhyou2507@gmail.com/Pipeline_Complete_Documentation.docx"

try:
    doc = Document(docx_path)
    
    # Extract all paragraphs
    all_text = []
    for para in doc.paragraphs:
        if para.text.strip():  # Only non-empty paragraphs
            all_text.append(para.text.strip())
    
    print(f"✅ Read DOCX file: {docx_path}")
    print(f"📊 Total paragraphs extracted: {len(all_text)}")
    print("\n📝 Sample text:")
    print(all_text[0][:200] + "...")
    
except FileNotFoundError:
    print(f"❌ File not found: {docx_path}")
    print("\n💡 Run 'Create_Documentation_DOCX' notebook first!")
    raise

# COMMAND ----------

# DBTITLE 1,Chunk text for RAG
# Step 2: Chunk text into smaller pieces for better search

print("\n✂️  Step 2: Chunking text for RAG...\n")

# Chunk strategy: Group paragraphs into logical sections
chunks = []
chunk_id = 1
current_chunk = []
chunk_size = 5  # paragraphs per chunk

for i, para in enumerate(all_text):
    current_chunk.append(para)
    
    # Create chunk every N paragraphs or at the end
    if len(current_chunk) >= chunk_size or i == len(all_text) - 1:
        chunk_text = "\n\n".join(current_chunk)
        
        # Determine category from content
        category = "General"
        if any(word in chunk_text.lower() for word in ["error", "fail", "exception"]):
            category = "Troubleshooting"
        elif any(word in chunk_text.lower() for word in ["schema", "table", "column"]):
            category = "Tables"
        elif any(word in chunk_text.lower() for word in ["pipeline", "layer", "bronze", "silver", "gold"]):
            category = "Pipeline"
        
        chunks.append({
            "id": chunk_id,
            "category": category,
            "text": chunk_text
        })
        
        chunk_id += 1
        current_chunk = []

print(f"✅ Created {len(chunks)} chunks")
print("\n📊 Chunk distribution:")

# Count by category
from collections import Counter
category_counts = Counter([c['category'] for c in chunks])
for cat, count in category_counts.items():
    print(f"   {cat}: {count} chunks")

# COMMAND ----------

# DBTITLE 1,Save to Delta table for Vector Search
# Step 3: Save chunks to Delta table

print("\n💾 Step 3: Saving chunks to Delta table...\n")

# Create DataFrame
chunks_df = spark.createDataFrame(chunks)

# Save to table
table_name = "retail_demo.rag.documentation_source"
spark.sql("CREATE SCHEMA IF NOT EXISTS retail_demo.rag")

chunks_df.write.mode("overwrite").saveAsTable(table_name)

print(f"✅ Saved to table: {table_name}")
print(f"📊 Total rows: {chunks_df.count()}")
print("\n📝 Sample data:")
display(chunks_df.limit(3))

# COMMAND ----------

# DBTITLE 1,Create Vector Search Endpoint
# Step 4: Create Vector Search Endpoint

print("\n🔌 Step 4: Creating Vector Search Endpoint...\n")

vsc = VectorSearchClient()

endpoint_name = "shivam_pipeline_assistant"

try:
    endpoint = vsc.get_endpoint(endpoint_name)
    print(f"✅ Endpoint already exists: {endpoint_name}")
except:
    print(f"📝 Creating endpoint: {endpoint_name}...")
    endpoint = vsc.create_endpoint(
        name=endpoint_name,
        endpoint_type="STANDARD"
    )
    print(f"✅ Endpoint created: {endpoint_name}")
    print("⏳ Endpoint is provisioning... (5-10 minutes)")
    print("   Check status: Compute → Vector Search")

print(f"\n📊 Endpoint: {endpoint_name}")

# COMMAND ----------

# DBTITLE 1,Create Vector Search Index
# Step 5: Create Vector Search Index with auto-embeddings

print("\n🔍 Step 5: Creating Vector Search Index...\n")

index_name = "retail_demo.rag.documentation_index"
source_table = "retail_demo.rag.documentation_source"

try:
    index = vsc.get_index(endpoint_name=endpoint_name, index_name=index_name)
    print(f"✅ Index already exists: {index_name}")
except:
    print(f"📝 Creating index: {index_name}...\n")
    
    index = vsc.create_delta_sync_index(
        endpoint_name=endpoint_name,
        index_name=index_name,
        source_table_name=source_table,
        pipeline_type="TRIGGERED",
        primary_key="id",
        embedding_source_column="text",  # Embed this column
        embedding_model_endpoint_name="databricks-bge-large-en"  # Foundation model
    )
    
    print(f"✅ Vector Search Index created: {index_name}")
    print("\n⏳ Index is syncing... (few minutes)")
    print("   Databricks will:")
    print("     1. Read 'text' column")
    print("     2. Generate embeddings (BGE model)")
    print("     3. Build vector index")

print("\n" + "="*80)
print("✅ VECTOR SEARCH SETUP COMPLETE!")
print("="*80)
print(f"\n🔍 Endpoint: {endpoint_name}")
print(f"📚 Index: {index_name}")
print(f"💾 Source: {source_table}")
print("🤖 Model: databricks-bge-large-en")
print("\n⚠️  Wait for endpoint + index to be ONLINE before testing!")

# COMMAND ----------

# DBTITLE 1,Test Vector Search (run after ONLINE)
# Step 6: Test Vector Search
# Run this AFTER endpoint and index are ONLINE!

print("\n🧪 Step 6: Testing Vector Search...\n")
print("⚠️  Only run after endpoint and index are ONLINE!\n")

try:
    index = vsc.get_index(endpoint_name=endpoint_name, index_name=index_name)
    
    # Test query 1
    print("\n🔍 Test Query 1: 'pipeline failed with NULL customer'")
    results = index.similarity_search(
        query_text="pipeline failed with NULL customer",
        columns=["id", "category", "text"],
        num_results=3
    )
    
    print("\nResults:")
    for i, row in enumerate(results.get('result', {}).get('data_array', []), 1):
        print(f"\n{i}. Similarity: {row[0]:.3f}")
        print(f"   Category: {row[2]}")
        print(f"   Text: {row[3][:150]}...")
    
    # Test query 2
    print("\n" + "="*80)
    print("\n🔍 Test Query 2: 'how to fix negative amount'")
    results = index.similarity_search(
        query_text="how to fix negative amount",
        columns=["id", "category", "text"],
        num_results=3
    )
    
    print("\nResults:")
    for i, row in enumerate(results.get('result', {}).get('data_array', []), 1):
        print(f"\n{i}. Similarity: {row[0]:.3f}")
        print(f"   Category: {row[2]}")
        print(f"   Text: {row[3][:150]}...")
    
    print("\n" + "="*80)
    print("✅ Vector Search working!")
    print("💡 Ready for Genie Space!")
    print("="*80)
    
except Exception as e:
    print(f"❌ Error: {str(e)}")
    print("\nCheck:")
    print("  1. Endpoint is ONLINE (Compute → Vector Search)")
    print("  2. Index is synced")
    print("  3. Wait a few minutes and try again")

# COMMAND ----------

# DBTITLE 1,Summary - Ready for Genie Space
# Final Summary

print("\n" + "="*80)
print("🎉 RAG SYSTEM READY FOR GENIE SPACE!")
print("="*80)

print("\n✅ What we created:\n")
print("1. 📝 DOCX File:")
print("   /Workspace/Users/shivam.singhyou2507@gmail.com/Pipeline_Complete_Documentation.docx")

print("\n2. 💾 Delta Table:")
print("   retail_demo.rag.documentation_source")
print("   (Source table with text chunks)")

print("\n3. 🔍 Vector Search:")
print(f"   Endpoint: {endpoint_name}")
print(f"   Index: {index_name}")
print("   (Semantic search with embeddings)")

print("\n4. 📊 Error Log:")
print("   retail_demo.monitoring.error_log")
print("   (Auto-populated when pipeline fails)")

print("\n" + "="*80)
print("💡 NEXT: CREATE GENIE SPACE")
print("="*80)

print("\nSteps to create Genie Space:")
print("\n1. Go to: Data Intelligence Platform → Genie")
print("\n2. Click: Create Space")
print("\n3. Name: Shivam_Pipeline_Assistant")
print("\n4. Add these tables:")
print("   • retail_demo.rag.documentation_source")
print("   • retail_demo.monitoring.error_log")
print("\n5. (Optional) Add Vector Search index for semantic search")
print("\n6. Ask Genie:")
print("   - What is the pipeline architecture?")
print("   - What errors happened today?")
print("   - How do I fix NULL customer_id?")
print("   - Why did my pipeline fail?")

print("\n" + "="*80)
print("🚀 YOU'RE DONE!")
print("="*80)

# COMMAND ----------

