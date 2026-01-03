# **Architectural Design and Implementation Strategy for a GitHub Search MCP Server**

## **1\. Executive Overview and Domain Scope**

The development of a Model Context Protocol (MCP) server designed to interface with GitHub represents a sophisticated engineering challenge that sits at the intersection of information retrieval, API orchestration, and semantic data structuring. The core objective—to accept a raw URL derived from a web search and transmute it into a structured, comprehensive Markdown document containing a "Question" and all associated "Answers" with metadata—requires a deep architectural understanding of GitHub’s evolving platform. This task is not merely one of simple data retrieval; it involves navigating the complex duality of GitHub’s interface, which spans the legacy resource-oriented REST API (v3) and the modern, graph-based GraphQL API (v4).

The necessity for this system arises from the limitations of generic web search engines when indexing dynamic, code-centric platforms. While a search engine can identify the existence of a relevant GitHub Issue or Discussion, it often fails to present the granular "Question and Answer" (Q\&A) structure in a format consumable by downstream AI models or MCP clients. A user encountering a GitHub URL needs immediate access to the problem statement (the Question), the community's proposed solutions (the Answers), the crowd-sourced validation of those solutions (Reaction Counts/Likes), and the authoritative resolution (Marked as Correct).

To achieve this functionality, the MCP server must act as an intelligent middleware layer. It must possess the logic to parse non-uniform input URLs, discern between entity types (Issues vs. Discussions), select the optimal transport protocol to minimize latency and API quota consumption, and reconstruct conversation threads that may span hundreds of comments and pagination cursors. Furthermore, the requirement to identify "correct" answers necessitates a nuanced handling of GitHub’s "Discussions" feature set versus the traditional "Issues" tracking system, as the concept of an accepted answer differs fundamentally between the two interaction models.1

This report provides an exhaustive, expert-level analysis of the methodologies required to convert a web-search-derived URL into a rich, semantic document. The analysis prioritizes operational resilience, data integrity, and strict adherence to the user's formatting requirements. We will explore the specific API endpoints, schema definitions, and algorithmic strategies necessary to build this system, with a particular focus on solving the "N+1 request" problem inherent in fetching reaction counts via legacy protocols.

## **2\. The Semantic Parsing of GitHub Resources**

The entry point for the MCP server is a URL provided by a standard web search. Web searches are agnostic to the underlying structure of the resource; they simply return a pointer to a page. Therefore, the first operational layer of the server must be a robust parsing engine capable of decomposing these URLs into their constituent API parameters: owner, repository, resource\_type, and resource\_id.

### **2.1 Anatomy of GitHub Resource URLs**

GitHub URLs follow a consistent hierarchy that maps directly to their data model, but variations exist that must be handled with regular expression precision. The extraction logic must account for the two primary resource types relevant to a Q\&A use case: Issues and Discussions.

The structural variance between these resources is subtle but architecturally significant. Issues use the /issues/ path segment, while Discussions use /discussions/. It is critical to note that while Pull Requests share the /pull/{number} namespace, the GitHub REST API historically treats Pull Requests as a subset of Issues.3 However, for a Search MCP focused on Q\&A retrieval, differentiating these entities at the parsing stage is vital to determine which API query template to employ downstream.

#### **2.1.1 Regex-Based Extraction Logic**

To reliably convert a raw string into API-ready parameters, specific regular expressions are required. The extraction mechanism must be resilient to query parameters (e.g., ?utm\_source=...), anchors (e.g., \#issuecomment-12345), and trailing slashes that web searches often append.5

Pattern for Issues:  
The regex must capture the owner, repository name, and the integer identifier.

Code snippet

https?://(?:www\\.)?github\\.com/(?P\<owner\>\[^/\]+)/(?P\<repo\>\[^/\]+)/issues/(?P\<number\>\\d+)

Pattern for Discussions:  
Similarly, for discussions, the path segment changes, but the parameter structure remains consistent.

Code snippet

https?://(?:www\\.)?github\\.com/(?P\<owner\>\[^/\]+)/(?P\<repo\>\[^/\]+)/discussions/(?P\<number\>\\d+)

The parsing logic must strictly enforce the \\d+ integer capture for the number parameter. GitHub identifiers for issues and discussions are always integers. If a URL contains non-numeric characters in this segment, it is likely a pointer to a branch, a file blob, or a wiki page, all of which are out of scope for this specific Q\&A retrieval requirement.6

### **2.2 Handling Ambiguity Between Issues and Pull Requests**

A nuanced detail in GitHub's architecture is the implementation of Pull Requests. In the REST API v3, every Pull Request is technically an Issue, but not every Issue is a Pull Request. Accessing the /repos/{owner}/{repo}/issues/{number} endpoint for a PR number will return metadata, but the response will include a pull\_request key to indicate its nature.8

However, the user's request focuses on "Questions" and "Answers." Pull Requests are primarily code review artifacts, whereas Issues and Discussions are the primary venues for general problem-solving and Q\&A. The architectural recommendation is to treat the URL structure as the source of truth for intent. If the URL contains /issues/, the system should process it as an Issue; if it contains /discussions/, it should be processed as a Discussion. This separation is reinforced by the GraphQL API, which provides distinct top-level fields for issue(...) and discussion(...) queries, allowing for more precise schema validation than the overloaded REST endpoints.1

### **2.3 URL Normalization and Validation**

Before API execution, the parsed parameters must undergo normalization.

1. **Case Insensitivity:** GitHub usernames and repository names are case-insensitive in URLs but often case-preserving in display. The API will handle casing variations, but normalizing to lowercase for internal caching (if implemented) is best practice.  
2. **Anchor Stripping:** A URL like .../issues/42\#issuecomment-888 points to a specific answer. The MCP server's goal is to retrieve *all* answers. Therefore, the parser must discard the \#issuecomment-888 fragment during the API request phase, although it could optionally store it to highlight the specific comment initially linked.9  
3. **Shortlink Expansion:** GitHub uses gists and other shortlinks (e.g., git.io). While rare in direct search results for issues, a robust system should be prepared to follow HTTP 301/302 redirects to resolve the canonical URL before parsing.8

## **3\. Protocol Selection: The REST vs. GraphQL Paradigm Shift**

The most significant architectural decision in this project is the choice of API protocol. The requirements specify retrieving the question, *all* answers (comments), the number of likes (reactions) per answer, and the "marked as correct" status. This specific combination of data points makes the choice between REST (v3) and GraphQL (v4) decisive.

### **3.1 The Limitations of REST for Rich Metadata Retrieval**

The GitHub REST API follows a strict resource-oriented design. To fulfill the user's request using REST, the MCP server would need to execute a "waterfall" of requests, leading to severe inefficiency and potential data inconsistency.

#### **3.1.1 The Waterfall Effect**

1. **Fetching the Question:** A GET request to /repos/{owner}/{repo}/issues/{number} is required to retrieve the issue body (the question) and initial metadata.8  
2. **Fetching the Answers:** A subsequent GET request to /repos/{owner}/{repo}/issues/{number}/comments is required to get the list of comments.11  
3. **Pagination:** If the thread exceeds 30 or 100 comments, subsequent requests to ?page=2, ?page=3, etc., are required.12

#### **3.1.2 The "Reaction" N+1 Problem**

The most critical failure point for REST in this context is the retrieval of "likes" (reactions). The standard issue comment object in the REST response does *not* consistently return a detailed summary of reactions that distinguishes them by type in a way that allows accurate counting of "likes" versus other emojis without caveats. While the application/vnd.github.squirrel-girl-preview media type introduced reaction summaries, the data is often aggregated or incomplete depending on the API version.13

To get an accurate count of specific reactions (like \+1 or heart) for *each* comment using REST, one might theoretically need to query the /reactions endpoint for each comment ID. For a thread with 50 comments, this would result in 1 (Issue) \+ 1 (Comments List) \+ 50 (Reactions) \= 52 API calls. This is the classic "N+1 request" problem, which is unacceptable for a performant MCP server. It drastically increases latency and consumes the API rate limit (5,000 requests per hour) at an unsustainable pace.15

### **3.2 The Superiority of GraphQL for Complex Retrieval**

The GitHub GraphQL API (v4) was specifically designed to solve the over-fetching and under-fetching problems inherent in REST. It allows for fetching complex, nested data structures in a single, atomic request. This capability is perfectly aligned with the MCP server's requirements.16

* **Unified Retrieval:** The system can fetch the Issue/Discussion details, the author info, and the first batch of comments in one call.  
* **Granular Reaction Data:** GraphQL allows us to query the reactionGroups field on the Comment node. This field provides exactly what is requested: a count of reactions grouped by content (e.g., THUMBS\_UP, HEART), allowing the server to calculate the "number of likes" per answer without *any* additional API calls.17  
* **"Marked as Answer" Detection:**  
  * For **Discussions**, GraphQL exposes a direct answer field on the Discussion object, or an isAnswer boolean on the Comment object, making detection of the "correct" answer trivial and semantically accurate.1  
  * For **Issues**, GraphQL allows checking the state (OPEN/CLOSED) and timeline events in the same query to infer resolution status.

### **3.3 Comparative Data Fetching Analysis**

The following table contrasts the operational complexity of both approaches for a standard request (1 Issue, 50 comments, reaction counts required):

| Feature | REST API Strategy | GraphQL API Strategy |
| :---- | :---- | :---- |
| **Request Count** | 2 to 50+ (depending on reaction fidelity) | 1 (Unified Query) |
| **Reaction Counts** | Included in summary (usually), but brittle | Explicitly requested via reactionGroups |
| **"Answered" Status** | Requires separate logic/endpoints for Discussions | Native field (answerChosenAt, answer) |
| **Payload Size** | Large (Over-fetching unused fields) | Optimized (Precise field selection) |
| **Pagination** | Link headers parsing (Page numbers) | Cursor-based (Reliable for live threads) |
| **Rate Limit Cost** | High (Multiple requests consume quota) | Calculated by node complexity (Efficient) |

**Architectural Decision:** The MCP server will utilize the **GraphQL API** as the primary data fetching mechanism. This approach minimizes latency, reduces the likelihood of hitting rate limits (by reducing the request count), and provides a schema-enforced guarantee of data structure.

## **4\. Schema Design for "Question & Answer" Extraction**

To execute the architectural vision, we must define the precise GraphQL schemas required. The query structure differs slightly between Issues and Discussions due to the divergent feature sets (specifically the "Answer" mechanism).

### **4.1 The "Discussion" Query Template**

For a Discussion, the user explicitly requested "whether the answer was marked as correct." GitHub Discussions supports this natively. The GraphQL query must request the discussion object and specifically the answer field.

The query structure is designed to retrieve the discussion metadata and a paginated list of comments. Note the specific request for reactionGroups within the comment nodes.

GraphQL

query ($owner: String\!, $name: String\!, $number: Int\!, $cursor: String) {  
  repository(owner: $owner, name: $name) {  
    discussion(number: $number) {  
      id  
      title  
      body  
      createdAt  
      url  
      author {  
        login  
      }  
      answer {  
        id  
        body  
        author {  
          login  
        }  
        createdAt  
        reactionGroups {  
          content  
          users {  
            totalCount  
          }  
        }  
      }  
      comments(first: 100, after: $cursor) {  
        totalCount  
        pageInfo {  
          hasNextPage  
          endCursor  
        }  
        nodes {  
          id  
          body  
          createdAt  
          author {  
            login  
          }  
          isAnswer  
          reactionGroups {  
            content  
            users {  
              totalCount  
            }  
          }  
        }  
      }  
    }  
  }  
}

**Schema Breakdown:**

* repository(owner: $owner, name: $name): The root entry point.  
* discussion(number: $number): Selects the specific discussion entity.  
* answer: This field specifically points to the comment marked as the solution. Retrieving id here allows for easy matching against the comment list later.18  
* comments(first: 100): Retrieves the first batch of answers. 100 is the maximum page size in GraphQL v4.  
* reactionGroups: This nested field returns an array of objects containing the reaction type (content) and the count (users.totalCount). This completely solves the requirement for "number of likes".17

### **4.2 The "Issue" Query Template**

Issues do not have an answer field in the same way Discussions do. The concept of a "correct answer" in an Issue is informal—usually, the issue is simply closed when resolved. However, the MCP server must still retrieve the question and answers (comments) with the same fidelity regarding reactions.

GraphQL

query ($owner: String\!, $name: String\!, $number: Int\!, $cursor: String) {  
  repository(owner: $owner, name: $name) {  
    issue(number: $number) {  
      id  
      title  
      body  
      state  
      createdAt  
      url  
      author {  
        login  
      }  
      comments(first: 100, after: $cursor) {  
        totalCount  
        pageInfo {  
          hasNextPage  
          endCursor  
        }  
        nodes {  
          id  
          body  
          createdAt  
          author {  
            login  
          }  
          reactionGroups {  
            content  
            users {  
              totalCount  
            }  
          }  
        }  
      }  
    }  
  }  
}

**Key Differences:**

* The answer field is absent because the Issue type does not support it.  
* The state field (OPEN/CLOSED) is requested to provide context on whether the "Question" is considered resolved by the maintainers.18

### **4.3 Reaction Group Schema Details**

The reactionGroups field is pivotal for satisfying the user's request for "likes." It returns a list of objects.

**Example Response Fragment:**

JSON

"reactionGroups":

The MCP server must parse this list. To determine the "number of likes," the logic should ideally sum the positive sentiment reactions. A strict interpretation might only count THUMBS\_UP, but in the context of GitHub, HEART, HOORAY, and ROCKET are also indicators of a "good" answer. The recommended logic is to sum these four categories to present a consolidated "Score" or "Likes" metric in the Markdown output.17

## **5\. The "Marked as Correct" Heuristic Challenge**

One of the explicit requirements is to indicate "whether the answer was marked as correct (if there is a way to detect it)." This requires a bifurcated strategy depending on the resource type.

### **5.1 Deterministic Detection in Discussions**

For **GitHub Discussions**, the platform has a native "Mark as Answer" feature. The GraphQL schema exposes this directly via the answer field on the Discussion object.

* **Mechanism:** When the query executes, if discussion.answer is not null, it returns the id of the accepted comment.  
* **Implementation:** During the processing of the comments list, the server checks if comment.id \== discussion.answer.id. If true, that specific answer is flagged. This is 100% deterministic and accurate.1

### **5.2 Heuristic Detection in Issues**

For **GitHub Issues**, there is no "Mark as Answer" button. Issues are "Closed" when resolved, but this does not explicitly point to a specific comment as the solution. The closure might be due to a code commit, a generic comment, or the issue being invalid.

**Why "Detection" is difficult for Issues:**

* An issue might be closed with a comment "Fixed in release v2.0". Is that comment the answer? Maybe.  
* An issue might be closed by a Pull Request. The "Answer" is the code change, not a comment text.  
* An issue might be closed as "Won't Fix".

Recommended Strategy:  
The MCP server should not attempt to guess which specific comment is the "Correct Answer" for an Issue, as this leads to high false-positive rates and user confusion. Instead, the Markdown output should clearly distinguish the status of the Question.

* If issue.state is CLOSED, the "Question" section should display a \*\*\*\* badge.  
* If issue.state is OPEN, it should display **\[OPEN\]**.  
* The output logic explicitly acknowledges that "Correct Answer" badges are reserved for Discussions where the data is semantic and verified. This adheres to the user's request clause "if there is a way to detect it"—for Issues, there is no reliable way to detect a specific comment as the answer via the API.18

## **6\. Pagination and High-Volume Data Retrieval**

A critical requirement is retrieving *all* answers. GitHub threads can grow to hundreds of comments. The API limits the number of nodes returned in a single GraphQL call (typically 100). Therefore, a single request is insufficient for popular threads.

### **6.1 Cursor-Based Pagination Logic**

The MCP server must implement a recursive or loop-based pagination strategy using GraphQL cursors. Unlike REST, which uses offsets (pages), cursors point to a specific node in the graph, ensuring that the traversal remains stable even if new comments are added while the scraper is running.19

**The Algorithm:**

1. **Initial Fetch:** Execute the query with first: 100 and after: null.  
2. **Process Buffer:** Extract the comments from data.repository.discussion.comments.nodes. Store them in a master list.  
3. **Check PageInfo:** Inspect data.repository.discussion.comments.pageInfo.  
   * Retrieve hasNextPage (boolean).  
   * Retrieve endCursor (string).  
4. **Loop Condition:** If hasNextPage is true:  
   * Update the query variable $cursor to the value of endCursor.  
   * Execute the query again (requesting *only* the comments connection to save bandwidth, though repeating the full query is stateless and easier).  
   * Append new nodes to the master list.  
5. **Termination:** Repeat until hasNextPage is false.

### **6.2 Comparison of Pagination: REST Link Headers vs. GraphQL Cursors**

| Feature | REST API | GraphQL API |
| :---- | :---- | :---- |
| **Indicator** | Link HTTP Header | pageInfo object in JSON body |
| **Method** | ?page=2, ?page=3 | after: "Y3Vyc29y..." |
| **Stability** | Vulnerable to drift (insertions shift offsets) | High stability (points to specific node) |
| **Complexity** | Requires parsing header string logic | Native JSON field access |
| **Limit** | Typically 30-100 items/page | Max 100 nodes/connection |

For the MCP server, GraphQL cursors provide a more robust mechanism for ensuring exactly-once processing of every comment in a rapidly updating thread.21

## **7\. Operational Resilience: Rate Limits and Error Handling**

A robust MCP server must anticipate failure. GitHub's API is aggressively rate-limited, and deep searches (retrieving hundreds of comments across multiple queries) can consume quota quickly.

### **7.1 Rate Limit Management Strategy**

GitHub's GraphQL API utilizes a "node limit" calculation (complexity score) for rate limiting, which is more complex than the REST API's simple request count. Each query costs points based on the number of fields and nodes requested.

Header Monitoring:  
The server must inspect the headers returned with every response 23:

* X-RateLimit-Remaining: The points left in the current window.  
* X-RateLimit-Reset: The UTC timestamp when the quota refreshes.

Backoff Algorithm:  
If the server receives a 429 Too Many Requests or 403 Forbidden (due to quota), it must implement a backoff strategy.

1. **Check Retry-After:** If this header is present, the process must sleep for the specified seconds.  
2. **Check X-RateLimit-Reset:** If Retry-After is absent, calculate the sleep time as ResetTime \- CurrentTime.  
3. **Exponential Fallback:** If headers are malformed, default to an exponential backoff (e.g., 1s, 2s, 4s, 8s) to prevent a "thundering herd" effect on the API.24

### **7.2 Error Handling and Data Integrity**

* **404 Not Found:** If the URL points to a deleted issue or a private repo without access, the API will return a 404\. The MCP server must catch this and return a polite Markdown error message (e.g., \> \*\*Error:\*\* Unable to retrieve data. The issue may be deleted or private.) rather than crashing or returning a blank page.26  
* **401 Bad Credentials:** Indicates an expired or invalid token. The server should fail fast and alert the user to check their MCP configuration.  
* **Sanitization:** The raw Markdown body from GitHub is generally safe, but standard input sanitization applies if the output is rendered in a web view. For a text-based Markdown report, raw retrieval is acceptable and desired to preserve code blocks.

## **8\. Transformation Logic: From JSON Graph to Markdown Document**

The final output is a Markdown document. The transformation layer converts the JSON response from GraphQL into the structured format requested by the user.

### **8.1 Structuring the Document**

The user specified a clear structure:

1. \# Question  
2. \# Answers  
3. \#\# Answer 1...

The transformation engine must iterate through the aggregated list of comments and format them.

#### **8.1.1 The Question Section**

This section consists of the Issue/Discussion Title and the main Body. We also inject metadata here to provide context.

**Markdown Template Strategy:**

# **Question: {Title}**

Author: {AuthorLogin} | Date: {CreatedAt} | Status: {State/Answered}  
{MarkedAsAnsweredBadge if applicable}  
{Body}

# ---

**Answers ({TotalCommentCount})**

#### **8.1.2 The Answers Section**

This section iterates through the retrieved comments. The user specifically asked for "number of likes" and "marked as correct."

Markdown Logic:  
Iterate through the comments array. For each comment:

1. **Calculate Likes:** Sum totalCount from the relevant reactionGroups (e.g., THUMBS\_UP \+ HEART \+ HOORAY \+ ROCKET).  
2. **Check Correctness:**  
   * *Discussions:* If comment.id \== discussion.answer.id, prepend a badge.  
   * *Issues:* No badge (as discussed in Section 5.2).  
3. **Format:**

## **Answer {Index}**

**User:** {UserLogin} | **Likes:** {LikeCount} {CorrectAnswerBadge}

{CommentBody}

### ---

**8.2 Handling "Rendered" vs. "Raw" Markdown**

The user asked for the output "as a markdown page." GitHub stores comments in Markdown.

* Requesting body in GraphQL returns the raw Markdown (e.g., \*\*bold\*\*).  
* Requesting bodyHTML returns the rendered HTML (e.g., \<b\>bold\</b\>).  
* Requesting bodyText returns plain text (e.g., bold).

For this MCP server, we **must** request body (Raw Markdown). This allows the MCP server to generate a Markdown file that preserves code blocks, bolding, lists, and links exactly as the author intended. If we fetched bodyHTML, we would have to reverse-engineer it back to Markdown or serve HTML, which violates the requirement for a "markdown page" output.

## **9\. Implementation Guide: Converting URL to API Call**

This section provides the concrete logic for the developer to bridge the gap between a Google search result and the GraphQL query.

### **9.1 The Conversion Algorithm**

1. **Input:** url\_string (e.g., https://github.com/foo/bar/issues/42)  
2. **Parse:** Apply Regex (Section 2.1) to extract owner="foo", repo="bar", number=42. Detect type="issue".  
3. **Select Template:**  
   * Since type is "issue", load the **Issue Query** template (Section 4.2).  
   * Inject variables: {"owner": "foo", "name": "bar", "number": 42}.  
4. **Execute:** Send POST request to https://api.github.com/graphql with Authorization header.  
5. **Pagination Loop:**  
   * Check data.repository.issue.comments.pageInfo.hasNextPage.  
   * If true, get endCursor and re-send query with after: "cursor...".  
   * Accumulate comments.  
6. **Transform:**  
   * Format Question header.  
   * Loop through comments, summing reactions, formatting Answer blocks.  
   * Identify "Correct Answer" (if Discussion) by matching IDs.  
7. **Output:** Return the concatenated string.

### **9.2 Python Implementation Details**

The implementation should use a robust HTTP library like requests or httpx in Python.

**Key Implementation Requirements:**

* **Token Handling:** The token must be passed securely.  
* **JSON Parsing:** GraphQL responses are JSON. The error handling must look for the errors top-level key in the JSON body, which indicates GraphQL-specific errors (like "Field not found" or "Validation failed") even if the HTTP status code is 200\.27  
* **Timeouts:** Network calls should always have a timeout (e.g., 10 seconds) to prevent the MCP server from hanging indefinitely if GitHub is unreachable.

## **10\. Conclusion and Strategic Recommendations**

Building a Search MCP server for GitHub requires a disciplined approach to API management. The research conclusively points to **GraphQL** as the necessary protocol to meet the user's specific requirements for reaction counts and nested answer data without incurring massive performance penalties.

### **10.1 Key Takeaways**

1. **GraphQL is Mandatory:** REST v3 cannot efficiently provide "likes per answer" for long threads due to the N+1 fetch problem.  
2. **Discussions\!= Issues:** The codebase must distinguish between these two entities to correctly identify "Accepted Answers." Attempting to apply "Answer" logic to Issues will fail.  
3. **Pagination is Critical:** "All answers" implies potential hundreds of records; cursor-based pagination must be implemented to ensure data completeness.  
4. **Metadata Enrichment:** The primary value of this tool lies in the metadata (likes, correctness), which transforms a raw dump of text into a prioritized, readable resource.

By following this architectural blueprint, the developer can construct a high-performance, resilient MCP server that delivers a superior reading experience for GitHub content, effectively bridging the gap between web search results and structured knowledge retrieval. This system will serve as a reliable conduit for AI models to access the vast repository of technical knowledge contained within GitHub's social coding platform.

#### **Works cited**

1. Using the GraphQL API for Discussions \- GitHub Docs, accessed January 2, 2026, [https://docs.github.com/en/graphql/guides/using-the-graphql-api-for-discussions](https://docs.github.com/en/graphql/guides/using-the-graphql-api-for-discussions)  
2. API to get the discussion that an issue was moved to \#45807 \- GitHub, accessed January 2, 2026, [https://github.com/orgs/community/discussions/45807](https://github.com/orgs/community/discussions/45807)  
3. Issue event types \- GitHub Docs, accessed January 2, 2026, [https://docs.github.com/en/rest/using-the-rest-api/issue-event-types](https://docs.github.com/en/rest/using-the-rest-api/issue-event-types)  
4. Identify relationship between issues and pull requests (v3 API) \#24492 \- GitHub, accessed January 2, 2026, [https://github.com/orgs/community/discussions/24492](https://github.com/orgs/community/discussions/24492)  
5. Extracting Repository Name from a Given GIT URL using Regular Expressions, accessed January 2, 2026, [https://www.geeksforgeeks.org/dsa/extracting-repository-name-from-a-given-git-url-using-regular-expressions/](https://www.geeksforgeeks.org/dsa/extracting-repository-name-from-a-given-git-url-using-regular-expressions/)  
6. Regular expression for git repository \- regex \- Stack Overflow, accessed January 2, 2026, [https://stackoverflow.com/questions/2514859/regular-expression-for-git-repository](https://stackoverflow.com/questions/2514859/regular-expression-for-git-repository)  
7. URL parsing regex.js \- GitHub Gist, accessed January 2, 2026, [https://gist.github.com/metafeather/202974](https://gist.github.com/metafeather/202974)  
8. REST API endpoints for issues \- GitHub Docs, accessed January 2, 2026, [https://docs.github.com/rest/issues/issues?apiVersion=2022-11-28](https://docs.github.com/rest/issues/issues?apiVersion=2022-11-28)  
9. How to get GitHub edit history of issue and issue comments via API? \- Stack Overflow, accessed January 2, 2026, [https://stackoverflow.com/questions/57658812/how-to-get-github-edit-history-of-issue-and-issue-comments-via-api](https://stackoverflow.com/questions/57658812/how-to-get-github-edit-history-of-issue-and-issue-comments-via-api)  
10. REST API endpoints for issue comments \- GitHub Docs, accessed January 2, 2026, [https://docs.github.com/rest/issues/comments](https://docs.github.com/rest/issues/comments)  
11. REST API endpoints for issue comments \- GitHub Docs, accessed January 2, 2026, [https://docs.github.com/en/rest/issues/comments](https://docs.github.com/en/rest/issues/comments)  
12. Using pagination in the REST API \- GitHub Docs, accessed January 2, 2026, [https://docs.github.com/en/rest/using-the-rest-api/using-pagination-in-the-rest-api](https://docs.github.com/en/rest/using-the-rest-api/using-pagination-in-the-rest-api)  
13. REST API endpoints for reactions \- GitHub Docs, accessed January 2, 2026, [https://docs.github.com/en/rest/reactions](https://docs.github.com/en/rest/reactions)  
14. REST API endpoints for team discussion comments \- GitHub Docs, accessed January 2, 2026, [https://docs.github.com/en/rest/teams/discussion-comments](https://docs.github.com/en/rest/teams/discussion-comments)  
15. REST API endpoints for reactions \- GitHub Docs, accessed January 2, 2026, [https://docs.github.com/en/rest/reactions/reactions](https://docs.github.com/en/rest/reactions/reactions)  
16. GitHub GraphQL API documentation, accessed January 2, 2026, [https://docs.github.com/en/graphql](https://docs.github.com/en/graphql)  
17. GitHub v4 API: Calculate content specific reaction count on a comment \- Stack Overflow, accessed January 2, 2026, [https://stackoverflow.com/questions/61503568/github-v4-api-calculate-content-specific-reaction-count-on-a-comment](https://stackoverflow.com/questions/61503568/github-v4-api-calculate-content-specific-reaction-count-on-a-comment)  
18. Objects \- GitHub Docs, accessed January 2, 2026, [https://docs.github.com/en/graphql/reference/objects](https://docs.github.com/en/graphql/reference/objects)  
19. GraphQL pagination with nested endCursors · community · Discussion \#106934 \- GitHub, accessed January 2, 2026, [https://github.com/orgs/community/discussions/106934](https://github.com/orgs/community/discussions/106934)  
20. GraphQL and Github API pagination with nested endCursors \- Reddit, accessed January 2, 2026, [https://www.reddit.com/r/github/comments/1amsdsu/graphql\_and\_github\_api\_pagination\_with\_nested/](https://www.reddit.com/r/github/comments/1amsdsu/graphql_and_github_api_pagination_with_nested/)  
21. Graphql API pagination issue \- Stack Overflow, accessed January 2, 2026, [https://stackoverflow.com/questions/70136467/graphql-api-pagination-issue](https://stackoverflow.com/questions/70136467/graphql-api-pagination-issue)  
22. GraphQL unexpectedly stops returning results while using cursor pagination · community · Discussion \#132644 \- GitHub, accessed January 2, 2026, [https://github.com/orgs/community/discussions/132644](https://github.com/orgs/community/discussions/132644)  
23. Rate limits for the REST API \- GitHub Docs, accessed January 2, 2026, [https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api)  
24. How to handle rate limits | OpenAI Cookbook, accessed January 2, 2026, [https://cookbook.openai.com/examples/how\_to\_handle\_rate\_limits](https://cookbook.openai.com/examples/how_to_handle_rate_limits)  
25. Handling API Rate Limits with Python: A Simple Recursive Approach \- Medium, accessed January 2, 2026, [https://medium.com/@balakrishnamaduru/handling-api-rate-limits-with-python-a-simple-recursive-approach-08349dd71057](https://medium.com/@balakrishnamaduru/handling-api-rate-limits-with-python-a-simple-recursive-approach-08349dd71057)  
26. Troubleshooting the REST API \- GitHub Docs, accessed January 2, 2026, [https://docs.github.com/en/rest/using-the-rest-api/troubleshooting-the-rest-api](https://docs.github.com/en/rest/using-the-rest-api/troubleshooting-the-rest-api)  
27. how to get total issues count of repository from github api ? · community · Discussion \#61508, accessed January 2, 2026, [https://github.com/orgs/community/discussions/61508](https://github.com/orgs/community/discussions/61508)