# **Architectural Specification and Deep Research Report: ArXiv-Enabled Search MCP Server**

## **1\. Executive Summary**

The integration of scientific repository access into Model Context Protocol (MCP) servers represents a pivotal advancement in the capabilities of Large Language Model (LLM) agents. As AI agents evolve from simple chat interfaces to autonomous research assistants, the ability to reliably identify, retrieve, and process academic literature becomes a non-negotiable requirement. The contemporary research landscape is dominated by arXiv, a repository that hosts millions of preprints across physics, mathematics, computer science, and biology. For an AI agent acting as a research assistant, the gap between finding a URL in a search result and ingesting the semantic content of that paper is a chasm filled with technical challenges: identifier ambiguity, strict API rate limiting, binary file management, and the complex translation of fixed-layout PDFs into fluid Markdown text.

This report provides a comprehensive architectural specification and deep research analysis for developing a search MCP server component specifically designed to handle arXiv preprints. The core objective, as defined by the system requirements, is to transform a raw URL obtained from a web search—often unstructured and variable in format—into a structured, machine-readable Markdown document suitable for context injection into an LLM. This process requires a sophisticated pipeline: robust identifier extraction using advanced regular expressions, adherence to arXiv’s programmatic access protocols (API usage and rate limiting), metadata harvesting via Atom XML feeds, binary PDF retrieval, and high-fidelity document-to-text conversion.

A critical engineering trade-off exists between processing speed and semantic fidelity, particularly regarding mathematical notation and complex layouts inherent to scientific papers. While traditional OCR (Optical Character Recognition) methods and modern Vision-Language Models (VLMs) like MinerU prioritize visual accuracy and LaTeX reconstruction, the requirement for "quick" conversion necessitates a focus on structure-aware text extraction techniques that bypass the heavy computational overhead of vision models. This report analyzes these trade-offs, recommending a tiered architecture that utilizes the export.arxiv.org namespace for stability and pymupdf4llm for rapid, structure-preserving conversion, while accounting for the nuances of LaTeX equation handling and legacy identifier support.

The following sections detail the taxonomy of arXiv identifiers, the mechanics of the arXiv API, strategies for compliant data harvesting, and the algorithmic approach to converting PDF binary streams into semantic Markdown. This document serves as the definitive reference for implementing the arXiv retrieval module within the broader Search MCP ecosystem.

## **2\. The Role of ArXiv in the Agentic AI Ecosystem**

To understand the architectural decisions required for an MCP server, one must first appreciate the operational environment of arXiv. Unlike modern web APIs designed for high-concurrency commercial use, arXiv is a legacy academic infrastructure hosted by Cornell University. It prioritizes stability and open access for human researchers over high-frequency automated trading or bot activity. This fundamental philosophy dictates the "Play Nice" policies that strictly govern how an MCP server must interact with the repository.

### **2.1. The "Search MCP" Paradigm**

The Model Context Protocol (MCP) standardizes how AI models interact with external data and tools. A "Search MCP" server acts as the bridge between the LLM's intent ("Find the latest paper on transformer attention mechanisms") and the chaotic reality of the open web. When a search tool returns a list of URLs, the LLM is typically blind to the content behind them. It sees https://arxiv.org/abs/1706.03762 and understands it is a paper, but it cannot read the methodology or results without a retrieval step.

The retrieval step is not merely a GET request. A raw HTML fetch of an arXiv abstract page provides metadata but no full text. A fetch of the PDF provides binary data that an LLM cannot natively process without significant token overhead or loss of structure. Thus, the MCP server must act as a transducer:

1. **Identification:** Recognizing that a generic URL points to a specific arXiv asset.  
2. **Negotiation:** Interacting with the arXiv API to get authoritative metadata (Title, Authors, Abstract) which is often cleaner than what is scraped from PDF text.  
3. **Transformation:** Converting the PDF into a token-efficient Markdown format that preserves the logical hierarchy of the document.

### **2.2. The Challenge of Scientific PDF Parsing**

Scientific documents represent the "hard mode" of document conversion. Unlike business letters or invoices, they are characterized by:

* **Multi-column layouts:** Text flows from the bottom of column A to the top of column B, interrupting the linear byte stream of the PDF file.  
* **Non-textual semantics:** Crucial information is encoded in mathematical formulas ($E=mc^2$) which, in a standard PDF text extraction, may appear as garbled Unicode characters or be missing entirely if they are rendered as vector paths.  
* **Floats:** Figures and tables are often placed at the top or bottom of pages, far removed from the text referencing them.

The requirement to perform this conversion "quickly" imposes a strict constraint. It rules out heavy, deep-learning-based OCR pipelines that render each page as an image and use vision encoders (like LayoutLM or Donut) to generate text. While these methods offer high fidelity for math, they are computationally expensive (seconds to minutes per paper on CPU). The architecture proposed here focuses on *text layer extraction*—reading the embedded character codes directly from the PDF file structure—which is orders of magnitude faster but requires careful handling of layout reconstruction.

## **3\. Taxonomy of ArXiv Identifiers and Extraction Logic**

The foundation of any arXiv integration lies in the accurate identification of the resource. Unlike standard web scraping, where a URL is simply a locator, in the arXiv ecosystem, the identifier (ID) is the primary key that unlocks metadata, version history, and alternative formats. A robust MCP server must possess a heuristic capability to normalize incoming URLs into canonical IDs.

### **3.1. Historical Evolution of Identifiers**

To build a regex pattern that is truly exhaustive, one must understand the two distinct eras of arXiv identifiers. A naive implementation that only looks for the modern format will fail on approximately 430,000 papers published prior to April 2007, representing a significant portion of the foundational scientific canon.

#### **3.1.1. The Legacy Scheme (Pre-April 2007\)**

Before April 2007, arXiv identifiers were category-dependent. They followed the structure archive.subject/YYMMNNN.1

* **Archive/Subject:** A string denoting the category, such as hep-th (High Energy Physics \- Theory), math, cs, or cond-mat. This string is composed of letters, hyphens, and occasionally dots (e.g., math.GT).  
* **YYMM:** The two-digit year and two-digit month. 9912 represents December 1999\.  
* **NNN:** A three-digit sequence number, zero-padded.

For example, hep-th/9912012 refers to the 12th paper submitted to High Energy Physics \- Theory in December 1999\. In some cases, subject classes were appended, such as math.GT/0309136. The API and URLs still support these legacy IDs, often using the format arxiv.org/abs/hep-th/9912012. Ignoring this format means an agent researching the history of string theory or early computer science would fail to retrieve seminal papers.

#### **3.1.2. The Modern Scheme (Post-April 2007\)**

In April 2007, arXiv decoupled the identifier from the subject classification to allow for easier reclassification and cross-listing. The new format is purely numerical: arXiv:YYMM.NNNN.2

* **YYMM:** Two-digit year and month. 0706 is June 2007\.  
* **NNNN:** Originally a 4-digit sequence number (starting at 0001).  
* **The 2015 Expansion:** Due to the explosion in submission rates, the sequence number was expanded to 5 digits in January 2015\.2 Thus, 1412.9999 is a valid 4-digit ID, but 1501.00001 is the standard 5-digit format moving forward.

This expansion is a critical edge case for regex design. A pattern that strictly enforces \\d{4} for the suffix will fail for every paper published after 2014\. Conversely, a pattern that enforces \\d{5} will fail for everything between 2007 and 2014\. The extraction logic must support \\d{4,5}.

#### **3.1.3. Versioning Suffixes**

Both schemes support versioning via a suffix vX, where X is an integer starting at 1 (e.g., 1912.01234v2). This suffix is critical for an MCP server.3

* **Implicit Latest:** If a user supplies a URL without a version (e.g., arxiv.org/abs/1912.01234), they almost always intend to see the most recent version.  
* **Explicit Version:** If a user supplies v1, it implies a specific need to reference the original manuscript, perhaps to check for changes or historical priority.

The MCP extraction logic must capture this suffix if present, as it dictates the specific PDF to be downloaded. However, when querying the API for *metadata* (title, authors), the version is often stripped to retrieve the general record, or kept to retrieve version-specific metadata.

### **3.2. Regex Pattern Engineering for Python**

Developing a regex pattern for Python's re module requires handling the variability of input URLs. Users might supply http://, https://, arxiv.org/abs/..., arxiv.org/pdf/..., or even export.arxiv.org/.... A generic web search might return a URL like https://arxiv.org/ftp/arxiv/papers/2109/2109.05857.pdf.

#### **3.2.1. The Unified Pattern Strategy**

A robust strategy involves a compiled regex that accounts for the boundary between the domain and the ID. We cannot simply search for \\d{4}\\.\\d{4,5} because similar patterns might appear in other URLs (e.g., IP addresses or dates). The pattern must be anchored to the arXiv domain or specific path indicators.

**Recommended Pattern Structure:**

1. **Domain Anchor:** (?:https?://)?(?:export\\.)?arxiv\\.org/ \- This handles http/https and the optional export subdomain.  
2. **Path Flexibility:** (?:abs|pdf|ftp|e-print)/ \- Matches the various access modes.  
3. **Modern ID Capture:** (\\d{4}\\.\\d{4,5}) \- Captures the YYMM.Number format.  
4. **Legacy ID Capture:** (\[a-zA-Z\\-\\.\]+\\/\\d{7}) \- Captures hep-th/9912001.  
5. **Version Suffix:** (v\\d+)? \- Optional capture for version.  
6. **Extension Stripping:** (?:\\.pdf)? \- Non-capturing group to ignore the file extension.

Combining these into a Python implementation requires creating a priority list or a complex OR group. Given that modern papers (post-2007) constitute the vast majority of search results today, the modern pattern should be checked first for efficiency.

Python

import re

def extract\_arxiv\_id(url\_string):  
    """  
    Extracts the canonical arXiv ID and version from a URL string.  
    Returns a tuple (arxiv\_id, version). Version may be None.  
    """  
    \# Pattern for Modern IDs (Post-2007)  
    \# Matches: 2109.05857, 2109.05857v1, 2109.05857.pdf  
    modern\_pattern \= r'(\\d{4}\\.\\d{4,5})(v\\d+)?'  
      
    \# Pattern for Legacy IDs (Pre-2007)  
    \# Matches: hep-th/9912012, math.GT/0309136  
    legacy\_pattern \= r'(\[a-zA-Z\\-\\.\]+\\/\\d{7})(v\\d+)?'  
      
    \# Search for modern first  
    match\_modern \= re.search(modern\_pattern, url\_string)  
    if match\_modern:  
        \# group(1) is the ID, group(2) is the version (e.g., 'v1') or None  
        return match\_modern.group(1), match\_modern.group(2)  
          
    \# Search for legacy second  
    match\_legacy \= re.search(legacy\_pattern, url\_string)  
    if match\_legacy:  
        return match\_legacy.group(1), match\_legacy.group(2)  
          
    return None, None

This logic is robust against variations like https://arxiv.org/pdf/2109.05857.pdf (extracts 2109.05857) and https://arxiv.org/abs/2109.05857v2 (extracts 2109.05857, v2).4

### **3.3. Resolving the "Latest" vs. "Specific" Ambiguity**

When a search result returns a URL like https://arxiv.org/abs/2109.05857, it refers to the abstract page of the *latest* version. However, https://arxiv.org/pdf/2109.05857 often redirects to the PDF of the latest version. The MCP server must decide whether to pin the version. For a general "search and retrieve" task, fetching the latest version is the standard behavior. If the URL specifically contains v1, the server should respect that. The arXiv API generally ignores the version suffix for metadata queries (returning the metadata for the article, which conceptually covers the work) unless the ID list explicitly includes it.

## **4\. ArXiv API Architecture and Protocol Compliance**

Once the identifier is extracted, the system must interface with arXiv's programmable infrastructure. It is imperative to distinguish between the interactive endpoints (intended for humans) and the API endpoints (intended for machines). Misusing the interactive arxiv.org domain for high-frequency automated requests can lead to IP bans.7

### **4.1. The Export Subdomain and API Endpoint**

The official endpoint for programmatic access is export.arxiv.org. While arxiv.org often works for simple GET requests, export.arxiv.org is specifically provisioned for bulk data and API traffic. This subdomain routes traffic to a dedicated cluster, separating bot activity from the interactive browsing experience of human researchers. Using this endpoint decreases the likelihood of being rate-limited during peak usage times.

**Base URL:** http://export.arxiv.org/api/query

### **4.2. Constructing the API Query**

For an MCP server responding to a search result, the primary query mode is query?id\_list=. This allows for precise retrieval of metadata for the specific paper found in the search. This is more efficient than search\_query because it bypasses the search index and retrieves the record directly by its primary key.9

**Parameters:**

* search\_query: Used for keyword searches (e.g., all:electron). Not primarily used when we already have the URL from a web search.  
* id\_list: A comma-delimited list of arXiv IDs. This is the target parameter for this use case.  
* start and max\_results: Paging parameters. For a single paper retrieval, start=0 and max\_results=1.

Example Construction:  
If the extracted ID is 2109.05857, the API call is:  
http://export.arxiv.org/api/query?id\_list=2109.05857  
If the ID includes a version (e.g., 2109.05857v1), it can still be passed to id\_list. The API behavior is subtle here 10:

* **Without Version:** Returns metadata for the article. The pdf link in the response usually points to the latest version.  
* **With Version:** Returns metadata specific to that version.

### **4.3. Rate Limiting and the "Play Nice" Policy**

ArXiv is hosted by Cornell University and operates on limited resources. They enforce a strict "Play Nice" policy to ensure availability for the global scientific community.

**Policy Details:**

* **Rate Limit:** The documentation specifies a limit of **one request every three seconds** for the legacy APIs.7  
* **Burst Allowances:** Some documentation suggests bursts of up to 4 requests per second are tolerated if followed by a sleep, but the safest, most durable implementation for an MCP server is a "Leaky Bucket" algorithm enforcing the 3-second interval.8  
* **User-Agent:** Custom User-Agent strings are **mandatory**. The generic requests library User-Agent (python-requests/x.y.z) is often blocked or throttled to prevent script kiddies from scraping the site. The User-Agent should follow the format: App Name/Version (contact-email). For example: ArxivMCP/1.0 (admin@example.com).12

Implementation Strategy:  
The MCP server should implement a global singleton rate limiter. Before any request to \*.arxiv.org is dispatched, the limiter checks the time since the last request. If less than 3 seconds have elapsed, the thread must sleep for the remainder of the interval. This prevents the MCP server from inadvertently triggering a 403 Forbidden response during a burst of user activity.

### **4.4. Handling HTTP Errors**

The arXiv API uses standard HTTP status codes, and the MCP server must handle them gracefully:

* **200 OK:** Successful retrieval.  
* **400 Bad Request:** Often due to query syntax errors or requesting \>30,000 results (unlikely for single retrieval).  
* **403 Forbidden:** Access denied, usually due to User-Agent blocking or rate limit violation.  
* **503 Service Unavailable:** The server is under load or down for maintenance. A robust system should implement an **Exponential Backoff** retry strategy (e.g., wait 3s, then 6s, then 12s) before giving up.14

## **5\. Metadata Ingestion and Parsing**

Before downloading the PDF, fetching metadata is crucial for generating the final Markdown report. The metadata provides the title, authors, abstract, and categories, which sets the context for the LLM.

### **5.1. Atom XML Parsing**

The API returns an Atom feed. Python's xml.etree.ElementTree is the standard tool for parsing this, though it requires careful handling of XML namespaces.15

**Namespaces:**

* Atom (default): http://www.w3.org/2005/Atom  
* ArXiv Extension: http://arxiv.org/schemas/atom

When using ElementTree, tags are prefixed with the namespace in curly braces. For example, the \<entry\> tag is {http://www.w3.org/2005/Atom}entry. The \<arxiv:primary\_category\> tag is {http://arxiv.org/schemas/atom}primary\_category.9

**Parsing Logic:**

1. **Parse Root:** root \= ET.fromstring(response.content)  
2. **Find Entry:** entry \= root.find('{http://www.w3.org/2005/Atom}entry'). If no entry is found, the ID was invalid.  
3. **Extract Fields:**  
   * *Title:* entry.find('{...}title').text \- This often contains newlines; use .replace('\\n', ' ') to normalize.  
   * *Summary (Abstract):* entry.find('{...}summary').text \- Critical for the LLM's summary capability.  
   * *Authors:* Iterate over entry.findall('{...}author') and extract {...}name.  
   * *Category:* Extract term attribute from {http://arxiv.org/schemas/atom}primary\_category. This helps the LLM understand if the paper is Math, CS, or Physics.  
   * *Published Date:* entry.find('{...}published').text

This metadata should be structured into a YAML frontmatter or a dedicated metadata section at the top of the final Markdown output.

## **6\. PDF Retrieval Strategy**

The search MCP needs to convert the paper to Markdown, which requires the binary PDF file.

### **6.1. Constructing the PDF URL**

While the Atom feed contains a \<link title="pdf"\> element, it is often more efficient and predictable to construct the URL directly if the ID is known. The Atom link might point to arxiv.org, whereas we prefer export.arxiv.org for bot traffic.

* **Standard URL:** https://export.arxiv.org/pdf/{ID}.pdf  
* **Note:** Appending .pdf is standard practice to ensure the server serves the binary with the correct MIME type (application/pdf).

### **6.2. Download Execution and Validation**

Using Python's requests library:

1. **Stream Download:** Use stream=True to handle large files without loading the entire binary into RAM immediately. This is important for server stability, as some papers (especially with high-res figures) can be 50MB+.  
2. **User-Agent:** Re-use the custom User-Agent defined in section 4.3.  
3. **MIME Type Validation:** Check the Content-Type header. It must be application/pdf. If it is text/html, the server likely returned an error page or a captcha challenge, indicating a failure in the extraction or rate limiting logic. This is a common failure mode where a bot assumes it got a PDF but actually got a "Access Denied" HTML page, leading to parser crashes later.

### **6.3. Temporary Storage**

Since the conversion libraries (discussed in Section 7\) typically operate on file paths, the downloaded stream should be written to a temporary file using Python's tempfile module. This ensures thread safety and automatic cleanup (if using NamedTemporaryFile with context managers). In a serverless environment (like AWS Lambda), writing to /tmp is the standard approach.

## **7\. PDF-to-Markdown Conversion Engine: Deep Research and Selection**

This is the core computational task. The requirement is to "quickly convert" the PDF into Markdown. This constraint immediately frames the choice of technology. We are analyzing the trade-off between **Heuristic Extraction** (fast, rule-based) and **Visual Extraction** (slow, model-based).

### **7.1. The Landscape of Converters**

The domain of PDF-to-Markdown conversion has exploded recently with the advent of RAG (Retrieval-Augmented Generation). We must choose the right tool for an MCP server that values responsiveness.

| Tool | Mechanism | Speed (Pages/Sec) | Math Fidelity | Hardware Req |
| :---- | :---- | :---- | :---- | :---- |
| **PyMuPDF4LLM** | Text Layer Extraction | High (\~10+) | Low (PDF specific) | CPU |
| **MinerU / Magic-PDF** | Layout Analysis \+ OCR | Low (\~0.2 \- 1.0) | High (LaTeX) | GPU / High RAM |
| **Marker** | Deep Learning Pipeline | Medium (\~2-5) | Medium-High | GPU Preferred |
| **Nougat** | Vision Transformer | Very Low | High | GPU Mandatory |

#### **7.1.1. PyMuPDF4LLM (The Recommended Fast Path)**

pymupdf4llm is a high-level wrapper around PyMuPDF (MuPDF).17

* **Mechanism:** It extracts text directly from the PDF's internal command stream. It uses font sizes and positions to heuristically determine headers, paragraphs, and list items. It does not "see" the page; it "reads" the draw commands.  
* **Speed:** Extremely fast (milliseconds to sub-second per page).18 It requires no heavy model loading.  
* **Pros:** Meets the "quickly" requirement perfectly. Supports image extraction. Good at standard layouts.  
* **Cons:** It extracts text as it is represented in the PDF layer. Complex LaTeX math equations are often stored as a jumble of characters and symbols in the PDF stream, not as LaTeX code. PyMuPDF4LLM will often render an equation as a sequence of non-semantic characters unless the PDF is tagged or the text layer is exceptionally clean. It does *not* natively reverse-engineer the pixel data of a formula back into LaTeX syntax.17

#### **7.1.2. MinerU / Magic-PDF (The Quality Path)**

MinerU (by OpenDataLab) is a state-of-the-art tool designed specifically for academic papers.20

* **Mechanism:** It uses a pipeline (PDF-Extract-Kit) that combines layout analysis models (detection of tables, figures, formulas) and OCR. It specifically detects formula regions and uses a Latex-OCR model to convert the pixels back into LaTeX code.  
* **Speed:** Significantly slower. On a CPU, it may take 5 seconds per page or more.22 On a GPU, it is faster but still heavier than PyMuPDF.  
* **Pros:** Incredible fidelity for scientific papers. Tables are converted to HTML/Markdown tables. Formulas are converted to LaTeX ($ E=mc^2 $).  
* **Cons:** High resource usage (RAM/VRAM). "Quickly" might be violated if the user is waiting for a 20-page paper to process on a CPU-only MCP server. The dependency chain is also massive (Torch, Detectron2), making the Docker container large.

#### **7.1.3. Marker and Nougat**

Marker is faster than Nougat but still relies on deep learning models.23 Nougat is a Transformer model that generates Markdown token-by-token from the page image. While accurate, Nougat is notoriously slow and prone to hallucination (repeating text) on long documents.

### **7.2. Selection for "Quick" Search MCP**

Given the user's explicit request for speed ("quickly convert"), **PyMuPDF4LLM** is the correct architectural choice for the default path. The latency of running a full OCR/VLM pipeline like MinerU or Marker inside a search loop is likely unacceptable for an interactive agent experience (which typically demands responses in \<10 seconds).

However, the report must acknowledge the limitation: **Mathematical formulas may be imperfect.** For a search MCP, the goal is often *relevance assessment* and *summary extraction*, for which text fidelity is paramount and perfect equation rendering is secondary. If the user requires "perfect LaTeX reconstruction," the system would need to switch to an asynchronous job using MinerU, but that is outside the scope of a synchronous "search" tool.

### **7.3. Implementation of PyMuPDF4LLM**

The conversion logic using pymupdf4llm is straightforward:

Python

import pymupdf4llm

def convert\_pdf\_to\_markdown(pdf\_path):  
    \# This single call performs layout analysis and markdown formatting  
    \# write\_images=False is set for speed and simplicity in text-based context  
    md\_text \= pymupdf4llm.to\_markdown(pdf\_path, write\_images=False)  
    return md\_text

Enhancements for Scientific Papers:  
To mitigate the math limitation, we can enable the write\_images flag. This extracts images and graphs, which are vital for understanding papers. The Markdown will link to these images. For an MCP server, sending images back might be complex (requiring hosting or base64 encoding).

* *Base64 Embedding:* pymupdf4llm supports embedding images as base64 strings directly in the Markdown (embed\_images=True). This allows the LLM to potentially "see" the charts if it is multimodal, without needing external file hosting.24 However, this balloons the token count. For a text-based search MCP, standard text extraction is preferred.

## **8\. System Architecture and Integration Workflow**

The final system architecture integrates these components into a linear pipeline.

### **8.1. The Pipeline Steps**

1. **Input:** User provides a query or string (e.g., "Check this paper [https://arxiv.org/abs/2305.10401](https://arxiv.org/abs/2305.10401)").  
2. **Regex Extraction:** The server applies the regex (\\d{4}\\.\\d{4,5}) and extracts 2305.10401.  
3. **Parallel Fetch (Optional but Recommended):**  
   * *Thread A:* Calls export.arxiv.org/api/query?id\_list=2305.10401. Parses XML for Title, Abstract, Authors, Date.  
   * *Thread B:* Calls export.arxiv.org/pdf/2305.10401.pdf. Downloads binary to temp\_file.pdf.  
   * *Synchronization:* Wait for both. If API fails, use PDF metadata (less reliable). If PDF fails, return Abstract only.  
4. **Conversion:** Run pymupdf4llm.to\_markdown("temp\_file.pdf").  
5. **Assembly:** Construct the final Markdown response.

### **8.2. Structuring the Final Markdown Outcome**

The output must be structured to help the LLM consume it efficiently. A raw dump of text is less effective than a structured document.

**Recommended Schema:**

Authors: \[Author 1, Author 2,...\]  
ArXiv ID: | Primary Category: \[Category\]  
Published:  
Link:

## **Abstract**

## **Full Text**

**Reasoning:**

* **Front-loading Metadata:** The LLM immediately knows the context (authors, date) before processing the heavy text.  
* **Abstract Separation:** The API-provided abstract is usually cleaner than the text extracted from the PDF (which might have hyphenation issues). Presenting the clean abstract first ensures high-quality summarization potential even if the model's context window cuts off the end of the paper.  
* **Visual Elements:** If embed\_images=True is used, the "Full Text" section will contain \!\[image\](data:image/png;base64...) tags, enabling multimodal capabilities.

### **8.3. Error Handling and Resilience**

* **Invalid ID:** If the regex finds nothing, return a clear "No arXiv ID found" message.  
* **Private/Withdrawn Papers:** The API will indicate if a paper is withdrawn. The MCP should parse the \<arxiv:comment\> or title to check for "Withdrawn".3  
* **PDF Parsing Failure:** If PyMuPDF fails (e.g., encrypted PDF, though rare on arXiv), catch the exception and return the Abstract with a note: "Full text conversion failed."  
* **Retry Logic:** Implement exponential backoff for 503 Service Unavailable errors from the API, as the arXiv server can be flaky under load.

## **9\. Detailed Implementation Guide: From URL to Markdown**

The following sections provide the deep-dive technical specifics required to implement the architecture defined above.

### **9.1. Advanced ArXiv API Usage**

The arXiv API is an interface to the central repository metadata.

#### **9.1.1. The API Query Endpoint**

The primary endpoint is http://export.arxiv.org/api/query.

* **Method:** GET or POST. GET is sufficient for single-paper retrieval.  
* **Namespace:** The XML response utilizes the Atom namespace.  
  * xmlns="http://www.w3.org/2005/Atom"  
  * xmlns:arxiv="http://arxiv.org/schemas/atom"

#### **9.1.2. Python Implementation Logic**

To retrieve the metadata, the urllib or requests library should be used.

* **User-Agent:** Define a variable HEADERS \= {'User-Agent': 'ArxivSearchMCP/1.0 (mailto:your\_email@example.com)'}.  
* **Request:** response \= requests.get(url, headers=HEADERS).  
* **Status Check:** response.raise\_for\_status() to handle 4xx/5xx errors.

#### **9.1.3. Parsing the Atom Feed**

The response is an XML string.

1. **Import:** import xml.etree.ElementTree as ET  
2. **Root:** root \= ET.fromstring(xml\_data)  
3. **Namespace Dict:** ns \= {'atom': 'http://www.w3.org/2005/Atom', 'arxiv': 'http://arxiv.org/schemas/atom'}  
4. **Extracting the Entry:** entry \= root.find('atom:entry', ns)  
5. **Data Points:**  
   * Title: entry.find('atom:title', ns).text.strip()  
   * Abstract: entry.find('atom:summary', ns).text.strip()  
   * Published Date: entry.find('atom:published', ns).text  
   * DOI: entry.find('arxiv:doi', ns).text (if available)

### **9.2. PDF Acquisition Logic**

Once the ID is confirmed via the API, the PDF is fetched.

* **URL Construction:** pdf\_url \= f"https://export.arxiv.org/pdf/{arxiv\_id}.pdf"  
* **Stream Handling:**  
  Python  
  import requests  
  import tempfile

  with requests.get(pdf\_url, headers=HEADERS, stream=True) as r:  
      r.raise\_for\_status()  
      with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp\_pdf:  
          for chunk in r.iter\_content(chunk\_size=8192):  
              tmp\_pdf.write(chunk)  
          temp\_pdf\_path \= tmp\_pdf.name

  * *Insight:* Using delete=False allows the file to persist long enough for the conversion tool to read it. It must be manually deleted (os.remove) after conversion to prevent disk bloat.

### **9.3. Conversion Logic with PyMuPDF4LLM**

The library pymupdf4llm simplifies the complex task of PDF parsing.

* **Installation:** pip install pymupdf4llm  
* **Execution:**  
  Python  
  import pymupdf4llm

  \# Convert to Markdown  
  \# write\_images=False ensures speed and text-only output if bandwidth is a concern.  
  \# Set write\_images=True to get image references if the LLM can handle them.  
  markdown\_content \= pymupdf4llm.to\_markdown(temp\_pdf\_path)

* **Post-Processing:** The output from PyMuPDF might contain excessive newlines or page break artifacts (-----). A simple cleanup pass (e.g., text.replace('\\n\\n\\n', '\\n\\n')) can improve readability.

### **9.4. Final Output Construction**

The MCP server should return a structured string.

Python

final\_response \= f"""\# {metadata\['title'\]}

\*\*Authors:\*\* {', '.join(metadata\['authors'\])}  
\*\*Date:\*\* {metadata\['published'\]}  
\*\*ArXiv ID:\*\* {arxiv\_id}

\#\# Abstract  
{metadata\['summary'\]}

\#\# Paper Content  
{markdown\_content}  
"""

This structure ensures the user (and the calling LLM) receives the high-level summary first, followed by the deep content, optimizing the "Time to First Token" utility of the response.

## **10\. Summary of Key Recommendations**

| Component | Recommendation | Reason |
| :---- | :---- | :---- |
| **Identifier Extraction** | Regex (\\d{4}\\.\\d{4,5})(v\\d+)? | Covers 99% of modern use cases; handles versioning. |
| **API Endpoint** | export.arxiv.org | Dedicated programmatic access; lower risk of blocking. |
| **Rate Limiting** | Leaky Bucket (1 req / 3 sec) | Strict compliance with arXiv Terms of Use. |
| **User-Agent** | Custom (Name/Email) | Required to identify traffic and avoid 403 errors. |
| **Conversion Tool** | pymupdf4llm | Fastest conversion; sufficient structure for search contexts. |
| **Output Format** | Structured Markdown | Separates Metadata/Abstract from Body for better LLM parsing. |

By adhering to this specification, the search MCP server will provide a robust, fast, and compliant bridge between the vast knowledge of the arXiv repository and the reasoning capabilities of modern AI agents. The architecture prioritizes speed and stability, utilizing rigorous protocol adherence and efficient conversion algorithms to deliver scientific insight at the speed of thought.

#### **Works cited**

1. Search for articles \- arXiv info, accessed January 2, 2026, [https://info.arxiv.org/help/find.html](https://info.arxiv.org/help/find.html)  
2. arXiv Identifier \- arXiv info, accessed January 2, 2026, [https://info.arxiv.org/help/arxiv\_identifier.html](https://info.arxiv.org/help/arxiv_identifier.html)  
3. Submission Version Availability \- About arXiv, accessed January 2, 2026, [https://info.arxiv.org/help/versions.html](https://info.arxiv.org/help/versions.html)  
4. Regular expression to extract URL from an HTML link \- Stack Overflow, accessed January 2, 2026, [https://stackoverflow.com/questions/499345/regular-expression-to-extract-url-from-an-html-link](https://stackoverflow.com/questions/499345/regular-expression-to-extract-url-from-an-html-link)  
5. URL regex Python \- UI Bakery, accessed January 2, 2026, [https://uibakery.io/regex-library/url-regex-python](https://uibakery.io/regex-library/url-regex-python)  
6. Matching arxiv regular expression in Python \- regex \- Stack Overflow, accessed January 2, 2026, [https://stackoverflow.com/questions/69985696/matching-arxiv-regular-expression-in-python](https://stackoverflow.com/questions/69985696/matching-arxiv-regular-expression-in-python)  
7. Downloading large number of PDFs \- Google Groups, accessed January 2, 2026, [https://groups.google.com/g/arxiv-api/c/WS7hR2A0OBM](https://groups.google.com/g/arxiv-api/c/WS7hR2A0OBM)  
8. arXiv Bulk Data Access, accessed January 2, 2026, [https://info.arxiv.org/help/bulk\_data.html](https://info.arxiv.org/help/bulk_data.html)  
9. arXiv API User's Manual, accessed January 2, 2026, [https://info.arxiv.org/help/api/user-manual.html](https://info.arxiv.org/help/api/user-manual.html)  
10. arXiv identifier scheme \- information for interacting services, accessed January 2, 2026, [https://info.arxiv.org/help/arxiv\_identifier\_for\_services.html](https://info.arxiv.org/help/arxiv_identifier_for_services.html)  
11. Terms of Use for arXiv APIs, accessed January 2, 2026, [https://info.arxiv.org/help/api/tou.html](https://info.arxiv.org/help/api/tou.html)  
12. How to Export arXiv Papers with Python's Atom API | by Mukhlis Raza | Medium, accessed January 2, 2026, [https://mukhlisraza.medium.com/how-to-export-arxiv-papers-with-pythons-atom-api-e084c2970484](https://mukhlisraza.medium.com/how-to-export-arxiv-papers-with-pythons-atom-api-e084c2970484)  
13. robots.txt \- arXiv, accessed January 2, 2026, [https://arxiv.org/robots.txt](https://arxiv.org/robots.txt)  
14. Rethinking HTTP API Rate Limiting: A Client-Side Approach This work was supported by NSF CNS Award 2213672\. \- arXiv, accessed January 2, 2026, [https://arxiv.org/html/2510.04516v1](https://arxiv.org/html/2510.04516v1)  
15. xml.etree.ElementTree — The ElementTree XML API — Python 3.14.2 documentation, accessed January 2, 2026, [https://docs.python.org/3/library/xml.etree.elementtree.html](https://docs.python.org/3/library/xml.etree.elementtree.html)  
16. python \- Use xml.etree.elementtree to process xml with xmlns="http://www.w3.org/2005/Atom" \- Stack Overflow, accessed January 2, 2026, [https://stackoverflow.com/questions/75786783/use-xml-etree-elementtree-to-process-xml-with-xmlns-http-www-w3-org-2005-atom](https://stackoverflow.com/questions/75786783/use-xml-etree-elementtree-to-process-xml-with-xmlns-http-www-w3-org-2005-atom)  
17. PyMuPDF4LLM \- PyMuPDF documentation \- Read the Docs, accessed January 2, 2026, [https://pymupdf.readthedocs.io/en/latest/pymupdf4llm/](https://pymupdf.readthedocs.io/en/latest/pymupdf4llm/)  
18. I Tested 7 Python PDF Extractors So You Don't Have To (2025 Edition) \- Aman Kumar, accessed January 2, 2026, [https://onlyoneaman.medium.com/i-tested-7-python-pdf-extractors-so-you-dont-have-to-2025-edition-c88013922257](https://onlyoneaman.medium.com/i-tested-7-python-pdf-extractors-so-you-dont-have-to-2025-edition-c88013922257)  
19. Is there a way to recognize equation in pdf? \#763 \- GitHub, accessed January 2, 2026, [https://github.com/pymupdf/PyMuPDF/discussions/763](https://github.com/pymupdf/PyMuPDF/discussions/763)  
20. MinerU2.5: A Decoupled Vision-Language Model for Efficient High-Resolution Document Parsing \- Bin Wang, accessed January 2, 2026, [https://wangbindl.github.io/publications/MinerU2\_5.pdf](https://wangbindl.github.io/publications/MinerU2_5.pdf)  
21. Extract Any PDF with MinerU 2.5 (Easy Tutorial) \- Sonusahani.com, accessed January 2, 2026, [https://sonusahani.com/blogs/mineru](https://sonusahani.com/blogs/mineru)  
22. MinerU is an awesome but very slow \#1226 \- GitHub, accessed January 2, 2026, [https://github.com/opendatalab/MinerU/discussions/1226](https://github.com/opendatalab/MinerU/discussions/1226)  
23. datalab-to/marker: Convert PDF to markdown \+ JSON quickly with high accuracy \- GitHub, accessed January 2, 2026, [https://github.com/datalab-to/marker](https://github.com/datalab-to/marker)  
24. How to Convert PDFs to Markdown Using PyMuPDF4LLM and Its Evaluation, accessed January 2, 2026, [https://dev.to/m\_sea\_bass/how-to-convert-pdfs-to-markdown-using-pymupdf4llm-and-its-evaluation-kg6](https://dev.to/m_sea_bass/how-to-convert-pdfs-to-markdown-using-pymupdf4llm-and-its-evaluation-kg6)