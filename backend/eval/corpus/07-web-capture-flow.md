# Web capture flow

The web capture flow stores browser-provided knowledge without server-side scraping. A user sends
a URL, title, selected text, notes, and tags to `POST /capture`. The backend validates the URL,
creates a `bookmark` source, writes the captured passage as a document, chunks it, embeds it, and
invalidates hot search cache entries. Tags travel through the normal ingest path, so captured
passages can be filtered in search and cited in chat. The important privacy rule is that capture
uses text the user supplied; it does not crawl the page on the server.
