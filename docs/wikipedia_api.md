Yes — you can fetch *Wikipedia article content* via the **MediaWiki Action API** (the API behind Wikipedia), so you don’t need to scrape HTML pages.

A key detail: the API won’t give you the *entire browser-rendered page* (skin, menus, etc.) as one blob. Instead, you ask for the parts you want (article HTML, wikitext, sections, images, metadata, extracts, …). The Action API is exposed at the `api.php` endpoint, typically `https://<wiki>/w/api.php`. ([MediaWiki][1])

## 1) Start from a Wikipedia URL → derive the title

Given a URL like:

* `.../wiki/Pet_door` → title is `Pet_door`
* `.../w/index.php?title=Pet_door` → title is the `title=` parameter

That title is what you pass as `page=` (parse) or `titles=` (query). (The Action API overview shows examples using `page=Pet_door`.) ([MediaWiki][1])

---

## 2) Get “the page” as rendered HTML (article body)

Use **`action=parse`** and request `prop=text` (parsed HTML). MediaWiki explicitly documents that to retrieve HTML you set `prop=text`, and you can identify the page by `page=` or a specific revision by `oldid=`. ([MediaWiki][2])

```bash
curl -H 'User-Agent: MyApp/1.0 (contact: you@example.com)' \
'https://en.wikipedia.org/w/api.php?action=parse&page=Pet_door&prop=text&format=json&formatversion=2'
```

The response contains the article HTML in the `parse.text` field. ([MediaWiki][2])

### Useful add-ons

* Follow redirects: `redirects=1` is supported by `action=parse`. ([MediaWiki][3])
* Want sections/images/links/etc.? `action=parse` supports many `prop=` values (e.g., `sections`, `images`, `links`, …). ([MediaWiki][3])

---

## 3) Get the canonical source (wikitext)

If you want the raw article source, use **`action=query&prop=revisions`** and request revision `content`.

MediaWiki documents that you retrieve wikitext by setting `titles=` and `rvprop=content` (often with slots). ([MediaWiki][2])

```bash
curl -H 'User-Agent: MyApp/1.0 (contact: you@example.com)' \
'https://en.wikipedia.org/w/api.php?action=query&prop=revisions&titles=Pet_door&rvslots=*&rvprop=content&format=json&formatversion=2'
```

Notes:

* `rvprop=content` returns “Content of each revision slot” and (for performance) enforces tighter limits when you request content. ([MediaWiki][4])
* If you omit `rvslots`, content defaults to `main` in a backwards-compatible format; using slots is the modern approach. ([MediaWiki][4])

---

## 4) Get plain-text (or limited HTML) extracts (good for previews / summaries)

MediaWiki lists “TextExtracts” as a main way to retrieve plain text / limited HTML extracts. ([MediaWiki][2])

On Wikipedia, you can typically do:

```bash
curl -H 'User-Agent: MyApp/1.0 (contact: you@example.com)' \
'https://en.wikipedia.org/w/api.php?action=query&prop=extracts&titles=Pet_door&exintro=1&explaintext=1&format=json&formatversion=2'
```

(That uses the TextExtracts extension API described by MediaWiki.) ([MediaWiki][2])

---

## 5) Browser-based JavaScript (CORS) tip

If you call the Action API from a browser, you generally need to include an `origin` (or `crossorigin`) query parameter; for unauthenticated requests you can use `origin=*`. ([MediaWiki][1])

Example:

```js
fetch('https://en.wikipedia.org/w/api.php?action=parse&page=Pet_door&prop=text&format=json&origin=*')
```

---

## 6) Be a good API citizen (important on Wikimedia)

Wikimedia recommends:

* Set a descriptive **User-Agent** (or `Api-User-Agent` for some browser contexts). ([MediaWiki][5])
* Use **`maxlag`** for non-interactive/batch work to avoid hammering busy replicas. ([MediaWiki][5])
* Follow rate limiting / usage guidelines; limits can change and shouldn’t be circumvented. ([foundation.wikimedia.org][6])

---

## Optional: “I really just want HTML via an API”

Wikipedia also exposes REST endpoints (separate from Action API). The Action API page itself points out `/rest.php` and related REST bases for Wikimedia projects. ([MediaWiki][1])
If you tell me the exact output you want (full article HTML vs lead section vs cleaned text), I’ll point you to the most convenient endpoint + parameters.

[1]: https://www.mediawiki.org/wiki/API%3AAction_API "API:Action API - MediaWiki"
[2]: https://www.mediawiki.org/wiki/API%3AGet_the_contents_of_a_page "API:Get the contents of a page - MediaWiki"
[3]: https://www.mediawiki.org/wiki/API%3AParsing_wikitext "API:Parsing wikitext - MediaWiki"
[4]: https://www.mediawiki.org/wiki/API%3ARevisions "API:Revisions - MediaWiki"
[5]: https://www.mediawiki.org/wiki/API%3AEtiquette "API:Etiquette - MediaWiki"
[6]: https://foundation.wikimedia.org/wiki/Policy%3AWikimedia_Foundation_API_Usage_Guidelines "Policy:Wikimedia Foundation API Usage Guidelines - Wikimedia Foundation Governance Wiki"
