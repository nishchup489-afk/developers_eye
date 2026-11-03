Recommended execution order
Priority	Task	Decision
P0	Retry behavior	Test now
P0	Lease expiration and crash recovery	Test now
P0	Idempotent document persistence	Test now
P0	Multi-worker safety	Test now
P0	Basic content-quality validation	Test now
P1	Build the indexer	Next milestone
P2	Search retrieval and ranking	After indexer
P2	10,000+ URL load benchmark	After basic search works
P3	Large-scale optimization	Only when benchmarks reveal bottlenecks




Check whether each has a meaningful title, correctly extracted main content, valid canonical URL, suitable content type, and minimal navigation/sidebar boilerplate.

You don't need advanced AI-based quality scoring yet.

One useful measurement is:
\[
\text{Usable document rate}=\frac{\text{Usable sampled documents}}{\text{Total sampled documents}}\times100
\]