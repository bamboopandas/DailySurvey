from . import arxiv, github, hackernews, openreview, rss, semantic_scholar, webpage

COLLECTORS = {
    "arxiv": arxiv.collect,
    "github": github.collect,
    "hackernews": hackernews.collect,
    "openreview": openreview.collect,
    "rss": rss.collect,
    "semantic_scholar": semantic_scholar.collect,
    "webpage": webpage.collect,
}
