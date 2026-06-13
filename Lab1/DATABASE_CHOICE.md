# DATABASE_CHOICE.md

## My Choice: Azure Cosmos DB - No SQL API (Serverless tier)

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
