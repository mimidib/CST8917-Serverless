# Assignment 1: Serverless Computing — Critical Analysis

**Name:** Mimi Dib
**Student #:** 040829779
**Course:** CST8917 — Serverless Applications
**Assignment:** Serverless Computing: One Step Forward, Two Steps Back — Critical Analysis
**Date:** June 14, 2026

> Paper under review: Hellerstein, J. M., et al. (2019). _Serverless Computing: One Step Forward, Two Steps Back._ CIDR.

---

## Part 1: Paper Summary

The central argument of the paper is that serverless computing, as it existed in 2019, is a real improvement in some ways but a regression in others, which in my view, is what the authors mean by "one step forward, two steps back." The step forward is operational: Functions-as-a-Service (FaaS) gives developers automatic scaling, scale-to-zero, pay-per-use billing, and freedom from managing servers. The two steps back are architectural: Painfully ignoring the importance of efficient data processing, and stymying the development of distributed systems. The authors argue that the FaaS programming model is so restricted that it blocks an entire class of applications, especially data-intensive and distributed computing like machine learning model training in their case study (these require splitting one job across many workers that have to coordinate and share data to finish the job). It also pushes developers toward inefficient designs. Some examples were re-fetching the same data from remote storage on every invocation instead of keeping it local, or passing data between functions by writing to and reading back from slow storage like S3/DynamoDB, rather than direct communication. In their view, FaaS as designed actually holds back the natural evolution of cloud programming for the workloads that matter most.

Most of the paper is spent laying out the specific limitations. The first is the limited lifetime of a function. Functions are killed after a short window (around 15 minutes on AWS Lambda at the time), and any state they held is lost, so long-running or stateful work does not fit. The second is communication. The authors mention individual functions have no inbound network connectivity and no stable, directly-addressable identity, so they cannot talk to each other directly. They are forced to communicate through slow storage services (e.g., S3 or DynamoDB), which adds latency and cost, and per-function network bandwidth is low. The authors describe this as an I/O bottleneck and a lack of direct addressability.

The third limitation, and the one the paper emphasizes most, is what they call the data-shipping anti-pattern. Good distributed data systems ship code to data, moving computation to where the data already lives. FaaS does the opposite: it ships data to the code, because each function invocation has to pull its data in from remote storage. This wastes bandwidth and undoes decades of database and systems work. The fourth limitation is hardware. FaaS offers only a narrow, uniform slice of CPU and memory, with no access to GPUs or other accelerators, which rules out machine learning and high-performance workloads. The fifth is that all of this makes distributed and stateful computing very hard. The authors back this up with case studies- including machine learning training, low-latency prediction serving via batching, and distributed computing- where FaaS implementations were dramatically slower and more expensive than the alternatives, mainly because of data shipping and the inability to communicate directly.

The paper closes with proposals for what future cloud programming should look like. They call for fluid code and data placement, so the platform can put computation close to data instead of forcing data to move. They call for access to heterogeneous, specialized hardware through proper abstractions. They call for long-lived, addressable components that can communicate directly rather than only through storage. They also argue for new, "disorderly" programming models built for distributed execution, drawing on ideas like declarative and dataflow programming.

---

## Part 2: Azure Durable Functions Deep Dive

### Orchestration Model

Durable Functions breaks an app into three roles, which is something we worked with directly in class. Client functions kick off an orchestration (usually from an HTTP trigger). Orchestrator functions are where you write the workflow in code and decide what runs and in what order. Activity functions do the actual work, like calling an API or writing to a database. The orchestrator doesn't do the heavy lifting itself, it just coordinates the activities and waits on their results. That's the big difference from plain FaaS, where every function is an isolated, stateless unit with no built-in way to work together. The paper complained that FaaS had no real way to compose functions into bigger stateful programs, and this orchestration model is basically Azure's answer to that. It's also worth saying this kind of orchestration is itself one of the bigger things that's changed since 2019 [2][3].

### State Management

Durable Functions handles state with event sourcing. Instead of saving a snapshot, it records every step the orchestration takes into a history using another member in the pattern, in something called an Event Store, which is an Azure Storage Table by default. This is essentially a function containing your workflow code called the "Orchestrator" that can run for days, weeks, or months even if the underlying server restarts. When it needs to pick back up, the durable function framework automatically intercepts the code execution, fetches the history and feeds it to your orchestrator function in order to rebuild where it left off, like a checkpoint. Because you just write normal code and the platform deals with the durability, the orchestration survives restarts and long waits without you wiring up any storage yourself. This directly addresses the paper's complaint that functions are stateless and lose everything when they end. Stateful serverless like this is one of the clearest things that's changed since 2019, though to be fair the functions underneath are technically still stateless, the state is just managed for you now [3][4].

### Execution Timeouts

Regular Azure Functions have an execution timeout (a few minutes on the Consumption plan). Orchestrator functions get around it because they don't actually stay running while they wait. When an orchestrator awaits an activity, it checkpoints its progress, gets unloaded from memory, then re-runs from the saved history and keeps going once the result is back. So an orchestration can run for hours or days without ever hitting the per-function limit, which answers the paper's complaint about short function lifetimes. The catch, and we saw this in the labs, is that activity functions are still normal functions, so each one still has to finish inside the regular timeout. Since 2019 those limits have also loosened: the Premium plan can be set to run unbounded but with caveats, while the Dedicated (App Service) plan is truly unbounded. One thing to watch though, regardless of Premium or Dedicated, if the function is kicked off by an HTTP request it still times out after 230 seconds (just under 4 minutes), a hard, non-configurable limit enforced by the Azure Load Balancer. To actually use an unbounded execution the function has to be triggered by something else, like a queue message, a timer, or a database change feed. And the per-invocation cap on Consumption is still there too [3][5][9].

### Communication Between Functions

The orchestrator and activity functions don't call each other directly. The Durable Task Framework moves their inputs and outputs through a task hub, which underneath is just Azure Storage queues and tables. You never set this plumbing up yourself, so it takes away the chore the paper described of manually using slow storage as a message bus. But I want to be honest about what it does and doesn't fix. The paper's deeper point was that functions talk through storage instead of over direct network connections, and Durable Functions is still storage-backed. It manages the middleman for you, but the middleman is still there, and that part hasn't really changed since 2019 [3][6].

### Parallel Execution (Fan-out / Fan-in)

Fan-out/fan-in lets an orchestrator fire off a bunch of activity functions at once and then wait for all of them before moving on. In code it's usually a list of activity calls gathered with something like `Task.WhenAll` (or `context.task_all` in Python). The framework keeps track of every parallel branch and reliably combines the results, even if things restart. This goes at the paper's worry that distributed computing is hard on FaaS, since splitting work across many workers and stitching the results back together becomes a built-in pattern instead of something you hand-build. That said, the work still flows through the same storage-backed mechanism, so the per-activity limits and the storage hop still apply [3][7].

---

## Part 3: Critical Evaluation

Durable Functions fixes a good chunk of what the paper complained about, but the way I see it, two of the biggest criticisms aren't really solved, they're just worked around.

The first is the data-shipping anti-pattern. The paper's strongest point was that FaaS ships data to code instead of shipping code to data, and Durable Functions doesn't change that. Activity functions still pull their inputs from external storage on every run, and the orchestrator passes data between steps through the task hub, which is storage too. There's no concept of putting the computation next to the data it needs, which is exactly the "fluid code and data placement" the authors asked for. The reason it sticks around is that Durable Functions is a layer sitting on top of ordinary Azure Functions and Azure Storage, so it improves how you coordinate functions but inherits the same compute-and-storage split that caused the problem in the first place. There's been some movement on this elsewhere since 2019 (things like S3 Object Lambda, or edge functions that run code closer to the data), but Durable Functions itself doesn't go there.

The second is the lack of direct, fast communication between components. The paper criticized functions for having no direct addressability and for being stuck talking through slow storage. Durable Functions hides this, but orchestrator-to-activity communication still goes through storage queues, so the latency and the architectural limitation are both still there. I'll give partial credit, because Durable Entities add long-lived, addressable stateful objects, which is pretty close to the "long-lived addressable agents" the authors wanted (Cloudflare's Durable Objects are another example that showed up after the paper). But even entities are backed by the same storage model, so the communication path hasn't fundamentally changed.

My verdict is that Durable Functions is real progress on some of the paper's criticisms, but not the kind of progress the authors were ultimately after. It genuinely solves the statelessness and coordination problems. State survives restarts, orchestrations run way longer than a single function timeout, and patterns like fan-out/fan-in and durable entities make stateful, distributed workflows something a normal developer can actually build. Those were real gaps in first-generation FaaS, and closing them matters.

What it doesn't do is rethink the underlying architecture. The authors weren't just asking for better orchestration, they were asking for code-to-data placement, direct communication, and access to specialized hardware, and Durable Functions delivers none of those. It makes the FaaS model a lot more usable, but it does it by building clever abstractions on top of the same compute-and-storage separation the paper objected to. Looking at the wider ecosystem since 2019, a lot of the real answers to the paper have actually come from stepping outside pure FaaS, things like container-based serverless (Azure Container Apps, Cloud Run, Fargate) and GPUs showing up on some serverless platforms. So I'd call Durable Functions strong engineering within the existing box rather than the step change the authors envisioned. For the orchestration-style apps most teams actually build, that trade-off is well worth it, but the paper's deepest criticisms are still open.

---

## References

1. Hellerstein, J. M., Faleiro, J., Gonzalez, J. E., Schleier-Smith, J., Sreekanti, V., Tumanov, A., & Wu, C. (2019). _Serverless Computing: One Step Forward, Two Steps Back._ CIDR. https://www.cidrdb.org/cidr2019/papers/p119-hellerstein-cidr19.pdf
2. Microsoft. _What are Durable Functions?_ https://learn.microsoft.com/azure/azure-functions/durable/durable-functions-overview
3. Microsoft. _Durable orchestrations._ https://learn.microsoft.com/azure/azure-functions/durable/durable-functions-orchestrations
4. Microsoft. _Durable Functions task hubs._ https://learn.microsoft.com/azure/azure-functions/durable/durable-functions-task-hubs
5. Microsoft. _Eternal orchestrations / timers._ https://learn.microsoft.com/azure/azure-functions/durable/durable-functions-eternal-orchestrations
6. Microsoft. _Performance and scale in Durable Functions._ https://learn.microsoft.com/azure/azure-functions/durable/durable-functions-perf-and-scale
7. Microsoft. _Durable Functions patterns (fan-out/fan-in)._ https://learn.microsoft.com/azure/azure-functions/durable/durable-functions-overview#fan-in-out
8. Microsoft. _Durable Entities._ https://learn.microsoft.com/azure/azure-functions/durable/durable-functions-entities
9. Microsoft. _Azure Functions scale and hosting._ https://learn.microsoft.com/en-us/azure/azure-functions/functions-scale

---

## AI Disclosure Statement

I used an AI assistant to set up the structure of this README, help me learn, and clarify a few Azure Durable Functions concepts during my research. I also used it to spell/grammar check, cross-check that the claims in my paper were accurate and verify I did not miss important updates since 2019.
