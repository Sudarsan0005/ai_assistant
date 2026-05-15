"""
Milvus Database Initialization and Migration Script

This script handles:
1. Creating Milvus collections if they don't exist
2. Schema migrations (adding fields, reindexing)
3. Data migration between collection versions
4. Database health checks
"""
import sys
from pathlib import Path
import logging
from typing import Optional

from pymilvus import connections, utility, Collection
from services.vector_store import MilvusVectorStore
from app.config import settings

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MilvusInitializer:
    """Handles Milvus database initialization and migrations"""
    
    def __init__(self, host: str = None, port: int = None):
        self.host = host or settings.MILVUS_HOST
        self.port = port or settings.MILVUS_PORT
        self.connected = False
    
    def connect(self):
        """Connect to Milvus"""
        try:
            connections.connect(
                alias="default",
                host=self.host,
                port=self.port
            )
            self.connected = True
            logger.info(f"✓ Connected to Milvus at {self.host}:{self.port}")
            return True
        except Exception as e:
            logger.error(f"✗ Failed to connect to Milvus: {e}")
            return False
    
    def check_health(self):
        """Check Milvus health"""
        if not self.connected:
            logger.error("✗ Not connected to Milvus")
            return False
        
        try:
            # Try to list collections
            collections = utility.list_collections()
            logger.info(f"✓ Milvus is healthy. Found {len(collections)} collections")
            return True
        except Exception as e:
            logger.error(f"✗ Milvus health check failed: {e}")
            return False
    
    def initialize_collections(self):
        """Initialize all required Milvus collections"""
        logger.info("\n" + "="*60)
        logger.info("Initializing Milvus Collections")
        logger.info("="*60)
        
        if not self.connected:
            if not self.connect():
                return False
        
        try:
            # Initialize vector store (this creates collections automatically)
            logger.info("\nCreating collections via MilvusVectorStore...")
            vector_store = MilvusVectorStore(
                host=self.host,
                port=self.port,
                collection_name=settings.MILVUS_COLLECTION_NAME,
                dim=settings.EMBEDDING_DIMENSION
            )
            
            logger.info("\n✓ Collections initialized successfully!")
            logger.info(f"  - Chunks collection: {settings.MILVUS_COLLECTION_NAME}")
            logger.info(f"  - Documents collection: {settings.MILVUS_COLLECTION_NAME}_documents")
            
            # Show collection stats
            self.show_collection_stats(vector_store.collection_name)
            self.show_collection_stats(vector_store.doc_collection_name)
            
            vector_store.close()
            return True
            
        except Exception as e:
            logger.error(f"\n✗ Failed to initialize collections: {e}")
            return False
    
    def show_collection_stats(self, collection_name: str):
        """Show statistics for a collection"""
        if not utility.has_collection(collection_name):
            logger.info(f"\n  Collection '{collection_name}' does not exist")
            return
        
        try:
            collection = Collection(collection_name)
            collection.load()
            
            num_entities = collection.num_entities
            logger.info(f"\n  Collection: {collection_name}")
            logger.info(f"    - Entities: {num_entities}")
            logger.info(f"    - Schema fields: {len(collection.schema.fields)}")
            
        except Exception as e:
            logger.error(f"  Error getting stats for {collection_name}: {e}")
    
    def drop_collection(self, collection_name: str, confirm: bool = False):
        """Drop a collection (dangerous!)"""
        if not confirm:
            logger.warning(f"⚠️  Skipping drop - confirmation required")
            return False
        
        try:
            if utility.has_collection(collection_name):
                utility.drop_collection(collection_name)
                logger.info(f"✓ Dropped collection: {collection_name}")
                return True
            else:
                logger.info(f"Collection '{collection_name}' does not exist")
                return False
        except Exception as e:
            logger.error(f"✗ Failed to drop collection: {e}")
            return False
    
    def reset_all_collections(self, confirm: bool = False):
        """Reset all collections (DANGEROUS - deletes all data!)"""
        if not confirm:
            logger.warning("\n⚠️  WARNING: This will delete ALL data!")
            logger.warning("To confirm, call with confirm=True")
            return False
        
        logger.info("\n" + "="*60)
        logger.info("RESETTING ALL COLLECTIONS")
        logger.info("="*60)
        
        chunk_col = settings.MILVUS_COLLECTION_NAME
        doc_col = f"{settings.MILVUS_COLLECTION_NAME}_documents"
        
        self.drop_collection(chunk_col, confirm=True)
        self.drop_collection(doc_col, confirm=True)
        
        logger.info("\n✓ All collections dropped")
        logger.info("Run initialize_collections() to recreate them")
        
        return True
    
    def migrate_schema(self, collection_name: str, migration_name: str):
        """
        Perform schema migration
        Note: Milvus doesn't support schema changes on existing collections
        Migration requires creating new collection and copying data
        """
        logger.info(f"\nMigrating collection: {collection_name}")
        logger.info(f"Migration: {migration_name}")
        
        # TODO: Implement specific migrations as needed
        logger.warning("Schema migration not yet implemented")
        logger.info("For schema changes, you need to:")
        logger.info("1. Create new collection with new schema")
        logger.info("2. Copy data from old to new collection")
        logger.info("3. Drop old collection")
        logger.info("4. Rename new collection")
    
    def disconnect(self):
        """Disconnect from Milvus"""
        if self.connected:
            connections.disconnect("default")
            self.connected = False
            logger.info("✓ Disconnected from Milvus")


def main():
    """Main initialization script"""
    print("\n" + "="*60)
    print("Milvus Database Initialization")
    print("="*60)
    
    initializer = MilvusInitializer()
    
    # Step 1: Connect
    print("\n1. Connecting to Milvus...")
    if not initializer.connect():
        print("\n❌ Failed to connect to Milvus")
        print("\nMake sure Milvus is running:")
        print("  docker-compose up -d")
        sys.exit(1)
    
    # Step 2: Health check
    print("\n2. Checking Milvus health...")
    if not initializer.check_health():
        print("\n❌ Milvus health check failed")
        sys.exit(1)
    
    # Step 3: Initialize collections
    print("\n3. Initializing collections...")
    if not initializer.initialize_collections():
        print("\n❌ Failed to initialize collections")
        sys.exit(1)
    
    # Success!
    print("\n" + "="*60)
    print("✅ Milvus initialization completed successfully!")
    print("="*60)
    print("\nYou can now:")
    print("  - Start the RAG application: python main.py")
    print("  - Upload documents via API")
    print("  - Query your documents")
    print("\nAPI Documentation: http://localhost:8000/docs")
    
    initializer.disconnect()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Milvus Database Initialization")
    parser.add_argument("--reset", action="store_true", help="Reset all collections (deletes data!)")
    parser.add_argument("--stats", action="store_true", help="Show collection statistics")
    parser.add_argument("--yes", action="store_true", help="Confirm destructive operations")
    
    args = parser.parse_args()
    
    initializer = MilvusInitializer()
    
    if not initializer.connect():
        sys.exit(1)
    
    if args.reset:
        if args.yes:
            initializer.reset_all_collections(confirm=True)
        else:
            print("⚠️  This will delete ALL data!")
            response = input("Type 'yes' to confirm: ")
            if response.lower() == 'yes':
                initializer.reset_all_collections(confirm=True)
            else:
                print("Reset cancelled")
    
    elif args.stats:
        chunk_col = settings.MILVUS_COLLECTION_NAME
        doc_col = f"{settings.MILVUS_COLLECTION_NAME}_documents"
        initializer.show_collection_stats(chunk_col)
        initializer.show_collection_stats(doc_col)
    
    else:
        main()
    
    initializer.disconnect()
