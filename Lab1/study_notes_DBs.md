# Choosing a Database for Storing JSON Analysis Results

---

## What are we choosing between?

| DB            | Data kind                 | Structure & Schema                                                                  | How to query/retrieve                  | JSON handling                       | Cost                               |
| ------------- | ------------------------- | ----------------------------------------------------------------------------------- | -------------------------------------- | ----------------------------------- | ---------------------------------- |
| Cosmos DB     | JSON documents            | Semi-structured — flexible schema, fields vary per document                         | Query by any field, filter, sort       | Native — JSON is the primary format | Higher — pay per RU (request unit) |
| Table Storage | Key-value pairs           | Semi-structured — flexible schema, columns vary per row but partition/row key fixed | Lookup by partition key + row key only | Not native — stored as properties   | Very low — cheapest option         |
| SQL Database  | Tables with relationships | Structured — strict schema, all rows must match defined columns and types           | SQL queries, joins, aggregations       | Supported but not primary format    | Medium — pay per DTU or vCore      |
| Blob Storage  | Whole files               | Unstructured — no schema, storage has no awareness of what is inside the file       | Retrieve whole file by name only       | Just a file — no querying inside it | Very low — pay per GB stored       |

---

## The databases in detail

### Cosmos DB

Microsoft's globally distributed NoSQL database. Fast anywhere in the world —
data can be replicated across multiple regions with low latency reads and writes.
Schema is flexible — data shape can evolve without migrations (adding new fields
to data without having to update the DB structure first).

A semi-structured multi-model database that supports multiple data models
through different APIs:

- **NoSQL API → Document model** — supports JSON documents, queried by the
  fields inside them. Most common use case.
- **Table API → Key-value model** — supports data with keys pointing to a value,
  queried using the keys only. Compatible with Table Storage (same key-value model)
  but adds global distribution, higher availability SLAs, and lower latency on top.
- **Cassandra API → Column-family model** — data organized in columns rather than
  rows. Used commonly for time series data (think Grafana/Prometheus) or analytics.
- **Gremlin API → Graph model** — data stored as nodes and edges (relationships
  between things). Good for social networks, fraud detection, anything where the
  connections matter as much as the data.

**Important: Graph vs SQL for relationships**
Both can represent relationships but differ in how they store and traverse them.
SQL uses foreign keys and joins — implied relationships reconstructed at query time
by matching IDs, not stored themselves. Works well for 2-3 levels of relationships
but gets slow and expensive going deeper (friend of friend of friend).
Graph model stores relationships as first class citizens — explicitly as an edge.
Traversal is fast at any depth. Choose Graph when relationships are the point of
the query.

**Serverless tier:**
Pay only when your database is doing work — billed per RU (request unit) consumed,
not for idle capacity. Best for dev environments or spiky unpredictable workloads.
For high consistent traffic, provisioned throughput becomes cheaper.

---

### Azure Table Storage

A simple, very cheap key-value store. Every row has a partition key, a row key,
and optional flexible columns. No enforced schema beyond those two fixed keys.

**When is it appropriate?**

- Simple lookups where you always know the key
- Storing IDs, session data, caches, flags
- When cost is the priority and query patterns are simple and predictable
- Example: storing already-processed Google review IDs for deduplication —
  perfect Table Storage use case

---

### Azure SQL Database

Fully managed relational database — SQL Server in the cloud without managing
the server. Strict schema, tables with defined columns and types, relationships
enforced through foreign keys.

**When would you choose SQL over NoSQL?**

- Your data has clear relationships between entities (users, orders, products)
- You need joins across multiple tables
- Your schema is well defined and stable — not changing frequently
- You need ACID transactions — financial data, order management, anything where
  data integrity is critical
- You need complex queries — aggregations, filtering across joined tables

---

### Azure Blob Storage

Object storage — designed for storing whole files, not querying data inside them.
Not a database in the traditional sense, but can act as lightweight storage for
simple use cases like storing a JSON file you read entirely into memory, CSVs you
process with Azure Data Factory, or raw exports before processing into a real DB.

**Trade-offs as a database:**

|     |                                                                                |
| --- | ------------------------------------------------------------------------------ |
| ✓   | Extremely cheap — pay per GB stored                                            |
| ✓   | Simple — no setup, no schema, no migrations                                    |
| ✓   | Good for files that are read whole and replaced whole                          |
| ✗   | Cannot query inside a file — must download the whole thing                     |
| ✗   | No indexing, no filtering, no sorting                                          |
| ✗   | Not suitable for concurrent writes — no transaction support                    |
| ✗   | Not suitable as data grows — reading a 1GB file to find one record is wasteful |

---

## Data structure types

| Type            | Meaning                                                    | Examples                 |
| --------------- | ---------------------------------------------------------- | ------------------------ |
| Structured      | Strict schema enforced, defined columns and types          | Azure SQL                |
| Semi-structured | Some shape but flexible, schema not enforced               | Cosmos DB, Table Storage |
| Unstructured    | No schema, raw bytes, storage has no awareness of contents | Blob Storage             |

---

## When to use what

| Scenario                                                 | Best choice             |
| -------------------------------------------------------- | ----------------------- |
| Complex JSON data, flexible schema, global scale         | Cosmos DB               |
| Simple key lookups, cheap storage, storing IDs           | Table Storage           |
| Relational data, joins, financial data, strict integrity | Azure SQL               |
| Files, images, CSVs, backups, raw exports                | Blob Storage            |
| Highly connected data, social graphs, fraud detection    | Cosmos DB — Gremlin API |
| Storing already-processed review IDs (deduplication)     | Table Storage           |
| Storing raw Outscraper CSV export                        | Blob Storage            |
| Storing and querying processed reviews                   | Cosmos DB               |

## My Choice: Azure Cosmos DB (Serverless tier)

---

## Justification

Analysis results come back as JSON documents — Cosmos DB stores JSON natively
as its primary format, meaning no transformation or mapping is needed between
what the function produces and what the database stores. The serverless tier
means I pay only per request unit (RU) consumed rather than provisioning
capacity upfront, making it essentially free at student/low traffic scale.
It requires no schema definition upfront — new fields can be added to documents
without migrations, which suits a project where the JSON structure may evolve.
Serverless is the right capacity mode here specifically because the workload is
intermittent and low-volume — occasional writes from the function with long idle
periods — so paying per request (with nothing billed while idle) fits far better
than reserving fixed throughput. Cosmos DB does offer a Free Tier (1000 RU/s +
25GB), but it applies only to provisioned-throughput accounts and is mutually
exclusive with Serverless, so it is not used here.

---

## Alternatives Considered

**Azure Table Storage — rejected**
Cheap and simple but JSON is not native — data gets stored as flat properties
not as a document. Querying is limited to partition key and row key lookups only,
meaning historical result queries would be severely limited.

**Azure SQL Database — rejected**
JSON is not the primary format and requires a fixed schema defined upfront.
Overkill for this use case — no relationships between entities that would
justify the complexity and cost of a relational database.

**Azure Blob Storage — rejected**
Not a real database. Cannot query inside stored files — to find one result
you would have to download the entire file. No indexing, no filtering,
not suitable as data grows.

---

## Cost Considerations

I chose the **Serverless** capacity mode — no provisioned capacity, billed only
per RU consumed. A point read of a ~1 KB document costs ~1 RU and a write has a
~5 RU minimum, so at this project's low, intermittent volume the cost is fractions
of a cent — effectively $0, with nothing billed while the database is idle.

Cosmos DB also offers a **Free Tier** (1000 RU/s + 25GB free per account) as an
alternative, but it applies only to *provisioned-throughput* accounts and is
**mutually exclusive with Serverless**. It also allows only one free-tier account
per subscription and is often unavailable in sandbox subscriptions. Because this
workload is idle-heavy rather than steady, Serverless is the better fit and the
Free Tier does not apply to this setup.

---

## Evaluation Against Criteria

| Criteria           | Cosmos DB verdict                                            |
| ------------------ | ------------------------------------------------------------ |
| Data structure     | JSON native — no transformation needed                       |
| Cost               | Serverless — pay per RU, ~$0 at this volume, nothing billed idle |
| Complexity         | No schema required — flexible, minimal setup                 |
| Scalability        | Serverless tier aligns perfectly with serverless functions   |
| Python SDK         | azure-cosmos SDK — well documented, works in Azure Functions |
| Query capabilities | Query by any field — historical results fully queryable      |
