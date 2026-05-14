# RAGFlow RAG Pipeline — Deep Code Analysis

## Overview

RAGFlow implements a multi-stage RAG pipeline across three main phases:

1. **Ingestion** — Parse raw files, chunk text, embed vectors, index into a doc store
2. **Retrieval** — Hybrid (sparse + dense) search, reranking, scoring
3. **Generation** — LLM answering with citation injection and reference linking

---

## Phase 1: Document Ingestion

### Entry Point — `rag/svr/task_executor.py → do_handle_task()`

Every uploaded document is processed as a background **task**. The orchestrator picks the right path based on `task_type`:

```python
# rag/svr/task_executor.py

async def do_handle_task(task):
    task_type = task.get("task_type", "")

    # Standard chunking path
    chunks = await build_chunks(task, progress_callback)

    # Embed the chunks
    token_count, vector_size = await embedding(chunks, embedding_model, task_parser_config, progress_callback)

    # Index into Elasticsearch / Infinity
    settings.docStoreConn.insert(chunks, index_name(task_tenant_id), task_dataset_id)
```

Special task types bypass standard chunking:
- `"raptor"` — hierarchical tree summarization (RAPTOR algorithm)
- `"graphrag"` — knowledge graph extraction
- `"dataflow"` — custom pipeline (visual flow builder)

---

### Step 1A: File Fetch → `build_chunks()` (`task_executor.py:264`)

```python
async def build_chunks(task, progress_callback):
    # 1. Fetch raw bytes from MinIO object storage
    bucket, name = File2DocumentService.get_storage_address(doc_id=task["doc_id"])
    binary = await get_storage_binary(bucket, name)

    # 2. Dispatch to the correct chunker based on parser_id
    chunker = FACTORY[task["parser_id"].lower()]
    # FACTORY maps: "naive", "paper", "book", "laws", "qa", "table", etc.

    cks = await thread_pool_exec(
        chunker.chunk,
        task["name"],
        binary=binary,
        from_page=task["from_page"],
        to_page=task["to_page"],
        lang=task["language"],
        callback=progress_callback,
        kb_id=task["kb_id"],
        parser_config=task["parser_config"],
        tenant_id=task["tenant_id"],
    )

    # 3. Assign a content hash as chunk ID, upload images to MinIO
    for ck in cks:
        d["id"] = xxhash.xxh64(
            (chunk["content_with_weight"] + str(d["doc_id"])).encode("utf-8")
        ).hexdigest()
        await image2id(d, ...)  # stores embedded images, returns img_id

    # 4. Optional: auto-generate keywords per chunk via LLM
    if task["parser_config"].get("auto_keywords", 0):
        cached = await keyword_extraction(chat_mdl, d["content_with_weight"], topn)
        d["important_kwd"] = re.split(r"[,，;；、\r\n]+", cached)

    return docs
```

---

### Step 1B: Parsing — `rag/app/naive.py → chunk()`

`chunk()` is the **universal entry function** for all file types. It selects the right parser and runs the file through chunking.

#### File-type dispatch

```python
# rag/app/naive.py

def chunk(filename, binary=None, from_page=0, to_page=..., lang="Chinese", callback=None, **kwargs):
    parser_config = kwargs.get("parser_config", {
        "chunk_token_num": 512,
        "delimiter": "\n!?。；！？",
        "layout_recognize": "DeepDOC",
    })

    if re.search(r"\.docx$", filename, re.IGNORECASE):
        sections = Docx()(filename, binary)           # custom Docx parser
        chunks, images = naive_merge_docx(sections, ...)

    elif re.search(r"\.pdf$", filename, re.IGNORECASE):
        # Choose PDF engine from PARSERS dict
        parser = PARSERS.get(layout_recognizer.strip().lower(), by_plaintext)
        # layout_recognizer options: "deepdoc", "mineru", "docling",
        #   "opendataloader", "tcadp parser", "paddleocr", "plaintext"
        sections, tables, pdf_parser = parser(filename, binary, ...)

    elif re.search(r"\.(csv|xlsx?)$", filename):
        sections = ExcelParser()(binary)

    elif re.search(r"\.(txt|py|js|java|...)$", filename):
        sections = TxtParser()(filename, binary, chunk_token_num, delimiter)

    elif re.search(r"\.(md|markdown|mdx)$", filename):
        sections, tables, section_images = Markdown(...)(filename, binary, ...)

    elif re.search(r"\.(htm|html)$", filename):
        sections = HtmlParser()(filename, binary, chunk_token_num)

    elif re.search(r"\.(json|jsonl)$", filename):
        sections = JsonParser(chunk_token_num)(binary)

    # After parsing, merge sections into token-limited chunks
    chunks = naive_merge(sections, chunk_token_num, delimiter, overlapped_percent)

    # Tokenize each chunk and create index documents
    res = tokenize_chunks(chunks, doc, is_english, pdf_parser)
    return res
```

#### PDF parsing pipeline (`Pdf` class wrapping `PdfParser`)

```python
class Pdf(PdfParser):
    def __call__(self, filename, binary=None, ...):
        # 1. OCR all pages → self.boxes (text blocks with coordinates)
        self.__images__(filename, zoomin, from_page, to_page, callback)

        # 2. Deep learning layout recognition (table / figure / text regions)
        self._layouts_rec(zoomin)

        # 3. Detect & extract table structure
        self._table_transformer_job(zoomin)

        # 4. Merge text fragments into readable lines
        self._text_merge(zoomin=zoomin)

        # 5. Extract table + figure blocks separately
        tbls = self._extract_table_figure(True, zoomin, True, True)

        # 6. Final vertical merge & reading-order sort
        self._naive_vertical_merge()
        self._concat_downward()

        # Returns: [(text, line_tag), ...], tables
        # line_tag encodes page_num + bounding box for position tracking
        return [(b["text"], self._line_tag(b, zoomin)) for b in self.boxes], tbls
```

#### DOCX parsing (heading-aware, table-aware)

```python
class Docx(DocxParser):
    def __call__(self, filename, binary=None, ...):
        self.doc = Document(filename)
        for block in self.doc._element.body:
            if block.tag.endswith("p"):        # paragraph
                lines.append({"text": clean(p.text), "image": image, "table": None})
            elif block.tag.endswith("tbl"):    # table
                title = self.__get_nearest_title(table_idx, filename)
                # Builds HTML table with hierarchical heading caption:
                # "DocName > Heading1 > Heading2"
                html = f"<table><caption>Table Location: {title}</caption>..."
                lines.append({"text": "", "image": None, "table": html})
```

---

### Step 1C: Chunking — `rag/nlp/__init__.py → naive_merge()`

After parsing, raw sections are merged into token-capped chunks.

```python
def naive_merge(sections, chunk_token_num=128, delimiter="\n。；！？", overlapped_percent=0):
    cks = [""]
    tk_nums = [0]

    def add_chunk(t, pos):
        tnum = num_tokens_from_string(t)
        if cks[-1] == "" or tk_nums[-1] > chunk_token_num * (100 - overlapped_percent) / 100:
            # Start a new chunk; prepend overlap from previous chunk
            overlapped = RAGFlowPdfParser.remove_tag(cks[-1])
            t = overlapped[int(len(overlapped) * (100 - overlapped_percent) / 100):] + t
            cks.append(t)
            tk_nums.append(tnum)
        else:
            cks[-1] += t       # append to current chunk
            tk_nums[-1] += tnum

    for sec, pos in sections:
        add_chunk("\n" + sec, pos)

    return cks
```

Key behaviours:
- Respects `chunk_token_num` (default 512 tokens, configurable per KB)
- Supports **overlapping** (`overlapped_percent`) — last N% of previous chunk prepended to next
- Supports custom delimiters (e.g., split on headings via backtick syntax `` `##` ``)

---

### Step 1D: Tokenization → `tokenize()` + `tokenize_chunks()`

```python
def tokenize(d, txt, eng):
    d["content_with_weight"] = txt                        # raw text, stored as-is
    t = re.sub(r"</?(table|td|caption|tr|th)...>", " ", txt)
    d["content_ltks"] = rag_tokenizer.tokenize(t)         # BM25-ready token string
    d["content_sm_ltks"] = rag_tokenizer.fine_grained_tokenize(d["content_ltks"])

def tokenize_chunks(chunks, doc, eng, pdf_parser=None, child_delimiters_pattern=None):
    res = []
    for ii, ck in enumerate(chunks):
        d = copy.deepcopy(doc)
        if pdf_parser:
            d["image"], poss = pdf_parser.crop(ck, need_position=True)  # crop page image
            add_positions(d, poss)  # stores page_num_int + bounding box
            ck = pdf_parser.remove_tag(ck)

        # Child chunking (hierarchical parent-child)
        if child_delimiters_pattern:
            d["mom_with_weight"] = ck       # parent chunk stored
            res.extend(split_with_pattern(d, child_delimiters_pattern, ck, eng))
            continue

        tokenize(d, ck, eng)
        res.append(d)
    return res
```

Each resulting document dict has:

| Field | Purpose |
|---|---|
| `content_with_weight` | Raw text for display |
| `content_ltks` | Tokenized string for BM25 full-text search |
| `content_sm_ltks` | Fine-grained tokens |
| `q_{N}_vec` | Dense embedding vector (added in next step) |
| `page_num_int` | Page numbers |
| `position_int` | Bounding box coordinates |
| `img_id` | Reference to image stored in MinIO |
| `important_kwd` | LLM-extracted keywords |
| `mom_id` | Parent chunk ID (for hierarchical retrieval) |
| `doc_id`, `kb_id` | Foreign keys to document & knowledge base |

---

### Step 1E: Embedding — `task_executor.py → embedding()`

```python
async def embedding(docs, mdl, parser_config=None, callback=None):
    tts = [d.get("docnm_kwd", "Title") for d in docs]   # filename titles
    cnts = [d["content_with_weight"] for d in docs]      # chunk content

    # Encode filenames once (broadcast to all chunks)
    vts, _ = await thread_pool_exec(mdl.encode, tts[0:1])
    tts = np.tile(vts[0], (len(cnts), 1))

    # Encode content in batches
    for i in range(0, len(cnts), settings.EMBEDDING_BATCH_SIZE):
        vts, c = await thread_pool_exec(batch_encode, cnts[i: i + BATCH_SIZE])
        cnts_batches.append(vts)

    # Weighted combination: title + content
    title_w = float(parser_config.get("filename_embd_weight", 0.1))
    vects = title_w * tts + (1 - title_w) * cnts   # 10% title, 90% content

    # Store as q_{dim}_vec on each doc
    for i, d in enumerate(docs):
        v = vects[i].tolist()
        d[f"q_{len(v)}_vec"] = v
```

The title weighting (default 10%) slightly biases retrieval toward documents whose filename matches the query.

---

## Phase 2: Retrieval

### Entry Point — `rag/nlp/search.py → Dealer.retrieval()`

```python
async def retrieval(self, question, embd_mdl, tenant_ids, kb_ids, page, page_size,
                    similarity_threshold=0.2, vector_similarity_weight=0.3,
                    top=1024, doc_ids=None, rerank_mdl=None, ...):

    # 1. Build search request
    req = {
        "kb_ids": kb_ids,
        "doc_ids": doc_ids,
        "question": question,
        "topk": top,
        "similarity": similarity_threshold,
        "available_int": 1,  # exclude disabled chunks
    }

    # 2. Hybrid search (BM25 + vector)
    sres = await self.search(req, index_names, kb_ids, embd_mdl, ...)

    # 3. Prune stale chunks (deleted docs not yet cleaned from vector store)
    sres = await self._prune_deleted_chunks(sres)

    # 4. Rerank
    if rerank_mdl:
        sim, tsim, vsim = self.rerank_by_model(rerank_mdl, sres, question, ...)
    else:
        sim, tsim, vsim = self.rerank(sres, question, ...)

    # 5. Filter by threshold, paginate
    sorted_idx = np.argsort(sim * -1)
    valid_idx = [i for i in sorted_idx if sim[i] >= similarity_threshold]

    # 6. Build result list
    for i in page_idx:
        ranks["chunks"].append({
            "chunk_id": id,
            "content_with_weight": chunk["content_with_weight"],
            "doc_id": chunk["doc_id"],
            "docnm_kwd": chunk["docnm_kwd"],
            "similarity": float(sim[i]),
            "vector_similarity": float(vsim[i]),
            "term_similarity": float(tsim[i]),
            "positions": chunk.get("position_int", []),  # ← used for reference highlighting
        })
```

---

### Step 2A: Hybrid Search — `Dealer.search()`

```python
async def search(self, req, idx_names, kb_ids, emb_mdl=None, ...):
    qst = req.get("question", "")

    # Full-text (BM25) query
    matchText, keywords = self.qryr.question(qst, min_match=0.3)

    if emb_mdl:
        # Dense vector query
        matchDense = await self.get_vector(qst, emb_mdl, topk, similarity)

        # Fusion: weighted_sum with weights "0.05 BM25 + 0.95 vector"
        fusionExpr = FusionExpr("weighted_sum", topk, {"weights": "0.05,0.95"})
        matchExprs = [matchText, matchDense, fusionExpr]
    else:
        matchExprs = [matchText]

    res = await thread_pool_exec(
        self.dataStore.search,
        src_fields, highlight_fields, filters,
        matchExprs, orderBy, offset, limit,
        idx_names, kb_ids,
    )

    # Fallback: if 0 results, retry with lower min_match=0.1
    if total == 0:
        matchText, _ = self.qryr.question(qst, min_match=0.1)
        matchDense.extra_options["similarity"] = 0.17
        res = await self.dataStore.search(...)
```

The fusion weights (5% BM25 / 95% vector) are set at the doc-store query level. After retrieval, the Python-side `rerank()` applies its own weighting.

---

### Step 2B: Reranking — `Dealer.rerank()`

```python
def rerank(self, sres, query, tkweight=0.3, vtweight=0.7, ...):
    _, keywords = self.qryr.question(query)

    # Assemble token lists: content + title (×2) + keywords (×5) + Q&A tokens (×6)
    for i in sres.ids:
        tks = (content_ltks + title_tks * 2 + important_kwd * 5 + question_tks * 6)
        ins_tw.append(tks)

    # Tag/PageRank feature scores (knowledge graph weighting)
    rank_fea = self._rank_feature_scores(rank_feature, sres)

    # Hybrid similarity: 30% BM25 + 70% vector cosine
    sim, tksim, vtsim = self.qryr.hybrid_similarity(
        sres.query_vector,
        ins_embd,
        keywords,
        ins_tw,
        tkweight, vtweight
    )

    return sim + rank_fea, tksim, vtsim
```

The keyword boosting strategy weights:
- `important_kwd` × 5 — LLM-extracted key terms
- `question_tks` × 6 — Q&A style question tokens (from QA chunker)
- `title_tks` × 2 — document title
- `content_ltks` × 1 — main text

This significantly improves precision for documents tagged with keywords or in Q&A format.

---

### Step 2C: Tag/PageRank Scoring — `_rank_feature_scores()`

```python
def _rank_feature_scores(self, query_rfea, search_res):
    # PageRank scores per chunk (set during graph construction)
    pageranks = [search_res.field[id].get(PAGERANK_FLD, 0) for id in search_res.ids]

    # Tag feature similarity (cosine between query tags and chunk tags)
    for i in search_res.ids:
        tag_feas = parse_tag_features(search_res.field[i].get(TAG_FLD))
        for t, sc in tag_feas.items():
            if t in query_rfea:
                nor += query_rfea[t] * sc
        rank_fea.append(nor / sqrt(denor) / q_denor)

    return np.array(rank_fea) * 10. + pageranks
```

Tags are extracted during indexing via `content_tagging` (LLM call) and stored as weighted features. At query time, the question is also tagged and compared.

---

### Step 2D: Parent-Child Retrieval — `retrieval_by_children()`

When hierarchical chunking is used (child_delimiter set), child chunks are matched but the **parent** chunk is returned for better context:

```python
def retrieval_by_children(self, chunks, tenant_ids):
    for id, cks in mom_chunks.items():
        chunk = self.dataStore.get(id, ...)   # fetch parent by mom_id
        d = {
            "content_with_weight": chunk["content_with_weight"],  # PARENT text
            "content_ltks": " ".join([ck["content_ltks"] for ck in cks]),  # child tokens
            "similarity": np.mean([ck["similarity"] for ck in cks]),
        }
        chunks.append(d)
```

---

## Phase 3: Answer Generation & Citation

### Entry Point — `api/db/services/dialog_service.py → async_ask()`

```python
async def async_ask(question, kb_ids, tenant_id, chat_llm_name=None, search_config={}):
    # 1. Load knowledge bases, resolve embedding model
    kbs = KnowledgebaseService.get_by_ids(kb_ids)
    embd_mdl = LLMBundle(...)
    chat_mdl = LLMBundle(...)

    # 2. Retrieve relevant chunks
    kbinfos = await retriever.retrieval(
        question=question,
        embd_mdl=embd_mdl,
        tenant_ids=tenant_ids,
        kb_ids=kb_ids,
        page=1, page_size=12,
        similarity_threshold=search_config.get("similarity_threshold", 0.1),
        vector_similarity_weight=search_config.get("vector_similarity_weight", 0.3),
        top=search_config.get("top_k", 1024),
        rerank_mdl=rerank_mdl,
        rank_feature=label_question(question, kbs),   # tag-based query expansion
    )

    # 3. Build prompt from retrieved chunks
    knowledges = kb_prompt(kbinfos, max_tokens)
    sys_prompt = PROMPT_JINJA_ENV.from_string(ASK_SUMMARY).render(
        knowledge="\n".join(knowledges)
    )

    # 4. Stream answer from LLM
    stream_iter = chat_mdl.async_chat_streamly_delta(sys_prompt, msg, {"temperature": 0.1})

    # 5. Post-process: inject citations
    final = decorate_answer(full_answer)
    yield final
```

---

### Step 3A: Knowledge Prompt Construction — `kb_prompt()`

```python
# rag/prompts/generator.py

def kb_prompt(kbinfos, max_tokens, hash_id=False):
    knowledges = []
    for i, ck in enumerate(kbinfos["chunks"][:chunks_num]):
        cnt = "\nID: {}".format(i)
        cnt += "\n├── Title: " + ck.get("docnm_kwd", "")
        cnt += "\n├── URL: " + ck.get("url", "")
        for k, v in (ck.get("document_metadata") or {}).items():
            cnt += f"\n├── {k}: {v}"
        cnt += "\n└── Content:\n"
        cnt += ck["content_with_weight"]
        knowledges.append(cnt)
    return knowledges
```

Each chunk is injected with a sequential ID, title, and optional metadata. The LLM is instructed to reference chunks by ID.

---

### Step 3B: Citation Injection — `Dealer.insert_citations()`

This is the mechanism that links answer sentences back to source chunks.

```python
# rag/nlp/search.py

def insert_citations(self, answer, chunks, chunk_v, embd_mdl, tkweight=0.1, vtweight=0.9):
    # 1. Split answer into sentences
    pieces = re.split(r"([^|][；。？!！\n]|[a-z][.?;!][ \n])", answer)

    # 2. Embed each answer sentence
    ans_v, _ = embd_mdl.encode(pieces_)

    # 3. Compute hybrid similarity between each sentence and each chunk
    thr = 0.63
    while thr > 0.3 and len(cites.keys()) == 0:
        for i, a in enumerate(pieces_):
            sim, tksim, vtsim = self.qryr.hybrid_similarity(
                ans_v[i],       # sentence embedding
                chunk_v,        # all chunk embeddings
                tokenize(pieces_[i]).split(),
                chunks_tks,
                tkweight, vtweight
            )
            mx = np.max(sim) * 0.99
            if mx < thr:
                continue
            # Top-4 matching chunks for this sentence
            cites[idx[i]] = [str(ii) for ii in range(len(chunk_v)) if sim[ii] > mx][:4]
        thr *= 0.8  # progressively lower threshold if no citations found

    # 4. Append [ID:N] markers into answer text
    for i, p in enumerate(pieces):
        res += p
        if i in cites:
            for c in cites[i]:
                res += f" [ID:{c}]"

    return res, seted  # seted = set of cited chunk indices
```

The citation system uses **sentence-level embedding similarity** (90% vector + 10% token) to match each generated sentence to the most relevant source chunk. The threshold starts at 0.63 and relaxes to ensure at least some citations are assigned.

---

### Step 3C: Reference Link Resolution

After citations are injected, the IDs are resolved to actual `doc_id` values:

```python
def decorate_answer(answer):
    answer, idx = retriever.insert_citations(
        answer,
        [ck["content_ltks"] for ck in kbinfos["chunks"]],
        [ck["vector"] for ck in kbinfos["chunks"]],
        embd_mdl,
        tkweight=0.7, vtweight=0.3
    )

    # idx = set of chunk indices that were actually cited
    idx = set([kbinfos["chunks"][int(i)]["doc_id"] for i in idx])

    # Only include documents that were actually cited
    recall_docs = [d for d in kbinfos["doc_aggs"] if d["doc_id"] in idx]
    kbinfos["doc_aggs"] = recall_docs

    refs = deepcopy(kbinfos)
    refs["chunks"] = chunks_format(refs)
    return {"answer": answer, "reference": refs}
```

The `chunks_format()` function normalizes each chunk reference into:

```python
{
    "id": chunk_id,
    "content": content_with_weight,
    "document_id": doc_id,
    "document_name": docnm_kwd,
    "positions": position_int,      # ← page + bounding box for PDF highlighting
    "image_id": img_id,             # ← image crop reference
    "similarity": ...,
    "vector_similarity": ...,
    "term_similarity": ...,
}
```

The `positions` field (list of `[page, x0, y0, x1, y1]` tuples) is what enables the frontend to **highlight the exact passage** in the PDF viewer.

---

## How Reference Highlighting Achieves High Accuracy

The system achieves accurate source attribution through several layered mechanisms:

### 1. Position Tracking During Parsing
Every text block extracted from PDFs carries a `_line_tag(b, zoomin)` which encodes the page number and bounding box. This survives all the way through chunking into `position_int` on the final index document.

### 2. Image Cropping
```python
# In tokenize_chunks():
d["image"], poss = pdf_parser.crop(ck, need_position=True)
```
For each chunk, a cropped image of that region of the PDF is generated and stored in MinIO. This allows the UI to show a visual snapshot of the source.

### 3. Sentence-Level Citation Matching
The `insert_citations()` function does not rely on string matching — it embeds each sentence of the LLM answer and runs hybrid similarity against all retrieved chunks. This catches paraphrased content that exact-match methods would miss.

### 4. Hierarchical Heading Context for Tables
When parsing DOCX tables, the code traverses all parent headings:
```python
def __get_nearest_title(self, table_index, filename):
    # Builds: "DocumentName > Heading1 > Heading2 > Heading3"
    hierarchy = [doc_name] + [t[1] for t in titles]
    return " > ".join(hierarchy)
```
This is injected as `<caption>Table Location: DocName > Section > Sub</caption>` so tables are always locatable in context.

### 5. PageRank & Tag Features
For knowledge graphs, chunks carry PageRank scores. For tagged corpora, chunks have tag-feature vectors. Both contribute to the final ranking score, so highly-connected or well-matched chunks bubble up even if their raw similarity is moderate.

### 6. Threshold Auto-Relaxation
The citation threshold starts at 0.63 and is multiplied by 0.8 on each pass until citations are found (floor ~0.3). This ensures the system always provides *some* attribution even for loosely-phrased answers, while preferring high-confidence matches first.

---

## Supporting Components

### `rag/nlp/query.py` — `FulltextQueryer`
Builds BM25 queries, handles Chinese/English tokenization differences, computes `hybrid_similarity` using numpy dot products on token-frequency vectors combined with cosine vector similarity.

### `rag/app/` — Domain-specific chunkers
Each file type has a dedicated chunker with tuned delimiters and heuristics:
- `paper.py` — academic papers (section detection, abstract separation)
- `laws.py` — legal documents (article/clause detection)
- `book.py` — books (chapter detection)
- `qa.py` — Q&A pairs (question as `question_kwd`, boosted ×6 at retrieval)
- `table.py` — spreadsheet-oriented chunking
- `resume.py` — structured resume parsing

### `deepdoc/vision/` — Vision models
- `layout_recognizer.py` — DL model to classify PDF regions (text / table / figure / header)
- `ocr.py` — OCR engine for scanned PDFs
- `table_structure_recognizer.py` — Detects row/column structure in table images

### `rag/graphrag/` — Knowledge graph
Extracts entities and relationships from documents, builds a graph, assigns PageRank scores to chunks based on connectivity. Used for `graphrag` task type and feeds `rank_feature` weighting during retrieval.

### `rag/raptor.py` — Hierarchical summarization
Clusters chunks by embedding similarity, generates LLM summaries per cluster, indexes summaries as higher-level chunks. Enables answering broad questions that span many chunks.