We need to start a new project called CodeKnowl. We want to start by creating a Product Design and PRD for a Code base Analyst AI Solution.

At A high level, we want a solution that can be installed on premise with no cloud-dependencies except access to code repositories. Given a list of one or more git repos (gitlab, github, bitbubucket, gitea, etc.) the solution will ingest the code repos, analyze them build a codegraph and knowledgebase of the code, and keep the knowledgebase and code graph up-to-date as commits are merged into the main branch.

Initally, we are looking at a three-node Kubernetes cluster built on HX 370 processors with 64GB of RAM each. We will use Qwen3-Coder-30B-A3B-Instruct-GGUF under lemonade-server to get high performance on an HX 370 SOC. We will also use lemonade-server and gpt-oss-20b-mxfp4-GGUF for a high speed but powerful general purpose LLM. On the third node we want to install CodeT5+. 

We want to use Memgraph for the code graph, Cypheer for the query language, and Qdrant for the vector database.  We want to use the Code Property Graph dessign pattern as our general implementation pattern.

While I have outlined the components above, we should do a buy vs. build exercise to determine if we should be using an existing solution. Part of our reason for the above is we already have GPT-OSS-20B and Qwen3-Coder-30B-A3B-Instruct running in our AI Cluster, along with qdrant.

For customers to levergage the code knowledge base, we want to expose our AI Software Analyst agent as a VS Code exxtension, possibly with CI Coding features similar to Kilo Code or Cline, but built on a local-model-first paradigm.

Because of the recent massive increase in hardware prices, we may not want to bring  afull product to market, but rather offer a recommended hardware configuration, and publish CodeKnowl as an open-source project available for commercially-permissive (MIT Licensed) use.

Please help me create a PRD for this project.
