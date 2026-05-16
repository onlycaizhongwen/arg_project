# Retrieval Funnel Boundary

The full target architecture uses a funnel of recall, pre-ranking, business intervention, and reranking.
Recall is allowed to collect a larger candidate set, but the system must not send huge candidate lists directly to a Cross-Encoder model.

The MVP deliberately implements only semantic vector recall and lightweight candidate truncation.
The search request exposes recall_size, pre_rank_size, and top_k so the candidate set is bounded before results are returned.
Business intervention such as SimHash deduplication, MinHash deduplication, MMR diversity, DPP diversity, and permission rules is planned for phase two.

Cross-Encoder reranking is also planned for phase two.
Until that stage is implemented, the search_plan response reports rerank_enabled as false.
