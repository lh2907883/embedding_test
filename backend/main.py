from config import QDRANT_STORAGE_PATH, COLLECTION_NAME, EMBEDDING_DIMENSION
from vector_store import VectorStore
from embedding_service import EmbeddingService
from chunking_service import ChunkingService
from tenant_manager import TenantManager


def main():
    store = VectorStore(QDRANT_STORAGE_PATH, COLLECTION_NAME, EMBEDDING_DIMENSION)
    embedder = EmbeddingService()
    chunker = ChunkingService()
    manager = TenantManager(store, embedder, chunker)

    # === 租户 A: 添加文档 ===
    print("=== 租户 A: 添加文档 ===")
    n = manager.add_document(
        tenant_id="tenant_a",
        doc_id="doc_1",
        text=(
            "Python是一种广泛使用的高级编程语言。它的设计哲学强调代码的可读性和简洁性。"
            "Python支持多种编程范式，包括面向对象、命令式、函数式和过程式编程。"
            "Python的标准库非常丰富，提供了大量的模块和函数，涵盖了文件操作、网络编程、"
            "数据库访问等多个领域。Python还有一个活跃的社区，提供了大量的第三方库和框架。"
        ),
        source="python_intro.txt",
    )
    print(f"  文档 doc_1 已添加，共 {n} 个 chunks")

    n = manager.add_document(
        tenant_id="tenant_a",
        doc_id="doc_2",
        text=(
            "机器学习是人工智能的一个分支，它使用算法和统计模型来让计算机系统从数据中学习。"
            "深度学习是机器学习的一个子领域，使用人工神经网络来模拟人脑的工作方式。"
            "常见的深度学习框架包括TensorFlow、PyTorch和Keras。"
        ),
        source="ml_intro.txt",
    )
    print(f"  文档 doc_2 已添加，共 {n} 个 chunks")

    # === 租户 B: 添加文档 ===
    print("\n=== 租户 B: 添加文档 ===")
    n = manager.add_document(
        tenant_id="tenant_b",
        doc_id="doc_1",
        text=(
            "向量数据库是一种专门用于存储和检索高维向量数据的数据库系统。"
            "它们通常使用近似最近邻搜索算法来快速找到与查询向量最相似的向量。"
            "常见的向量数据库包括Qdrant、Milvus、Pinecone和ChromaDB。"
            "向量数据库在推荐系统、语义搜索和RAG等应用中发挥着重要作用。"
        ),
        source="vector_db_intro.txt",
    )
    print(f"  文档 doc_1 已添加，共 {n} 个 chunks")

    # === 搜索测试：租户隔离验证 ===
    print("\n=== 搜索测试：租户 A 搜索 '深度学习' ===")
    results = manager.search("tenant_a", "深度学习框架", top_k=3)
    for r in results:
        print(f"  [{r.score:.4f}] {r.doc_id}/{r.chunk_id}: {r.text[:80]}...")

    print("\n=== 搜索测试：租户 B 搜索 '深度学习'（不应返回租户A的数据） ===")
    results = manager.search("tenant_b", "深度学习框架", top_k=3)
    for r in results:
        print(f"  [{r.score:.4f}] {r.doc_id}/{r.chunk_id}: {r.text[:80]}...")
    print("  (仅返回租户B自己的数据 — 租户隔离生效)")

    print("\n=== 搜索测试：租户 B 搜索 '向量数据库' ===")
    results = manager.search("tenant_b", "向量数据库的应用场景", top_k=3)
    for r in results:
        print(f"  [{r.score:.4f}] {r.doc_id}/{r.chunk_id}: {r.text[:80]}...")

    # === 更新文档测试 ===
    print("\n=== 更新文档测试：租户 A 更新 doc_1 ===")
    n = manager.update_document(
        tenant_id="tenant_a",
        doc_id="doc_1",
        text="Python 3.12 引入了更好的错误提示和性能优化。新版本大幅提升了解释器速度。",
        source="python_update.txt",
    )
    print(f"  文档 doc_1 已更新，共 {n} 个 chunks")

    results = manager.search("tenant_a", "Python新版本", top_k=1)
    for r in results:
        print(f"  [{r.score:.4f}] {r.doc_id}/{r.chunk_id}: {r.text[:80]}")

    # === 删除文档测试 ===
    print("\n=== 删除文档测试：租户 A 删除 doc_2 ===")
    manager.delete_document("tenant_a", "doc_2")
    results = manager.search("tenant_a", "机器学习", top_k=3)
    print(f"  删除后搜索 '机器学习' 结果数: {len(results)}")

    # === 清理 ===
    store.close()
    print("\n完成!")


if __name__ == "__main__":
    main()
