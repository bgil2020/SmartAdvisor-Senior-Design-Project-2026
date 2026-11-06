# SmartAdvisor Documentation Index

Welcome to the documentation for the **SmartAdvisor** academic planning and advising decision-support system.

---

## Core Documentation

| Document | Description |
| :--- | :--- |
| [Architecture Guide](architecture.md) | High-level system architecture, component boundaries, data flow, and runtime state management. |
| [API Reference](api.md) | Complete REST API specification for backend endpoints, request/response formats, and synthetic payloads. |
| [Development Guide](development.md) | Contributor setup, directory layout conventions, environment management, and branch workflows. |
| [Testing Guide](testing.md) | Automated testing suites (pytest & Node test runner), manual smoke checklists, and verification procedures. |
| [RAG Storage and Coverage Assessment](rag-storage-coverage-assessment.md) | Measured file/corpus costs, discovery coverage, deployment trade-offs, and the recommended pre-acquisition storage contract. |
| [RAG Operational Storage](rag-operational-storage.md) | Atomic accepted/corpus generations, safe import and recovery, runtime retriever swapping, and concurrency limits. |
| [Controlled Catalog Fetch-on-Miss](rag-catalog-acquisition.md) | Opt-in one-course catalog acquisition through `/conversation`, bounded source access, diagnostics, and reuse behavior. |
| [Controlled Exact-Mapping Syllabus Fetch-on-Miss](rag-syllabus-acquisition.md) | Opt-in exact-manifest syllabus acquisition, headless browser safety, validation, and failure behavior. |
| [Syllabus Acquisition Diagnostic Checkpoint](rag-syllabus-diagnostics.md) | Sanitized browser lifecycle diagnostics, offline defect findings, supported alternatives, and the live-verification approval gate. |
| [Offline Syllabus Parser Comparison](rag-syllabus-parser-comparison.md) | Saved-data comparison of the existing parser, Beautiful Soup, unavailable local alternatives, and public-representation evidence. |

---

## Component & Specialized Documentation

| Document | Location | Description |
| :--- | :--- | :--- |
| **Conversational Intent Classifier** | [backend/docs/conversational_intent_classifier.md](../backend/docs/conversational_intent_classifier.md) | Rule-based regex/keyword intent classification specification. |
| **Conversational Response Policy** | [backend/docs/conversational_response_policy.md](../backend/docs/conversational_response_policy.md) | Deterministic routing decision, safety boundaries, and engine handoff specification. |
| **Prompt Dataset Draft** | [docs/research/conversational_prompt_dataset_draft.md](research/conversational_prompt_dataset_draft.md) | Research draft and labeled evaluation prompts for conversational intents. |
| **Course Dataset Dictionary** | [data/data_dictionary.md](../data/data_dictionary.md) | Field definitions and metadata for `data/FAU_Courses.xlsx`. |
| **Course Description Collector** | [course-description-collector.md](course-description-collector.md) | Bounded manual acquisition, validation, acceptance, rollback, and future RAG handoff. |
| **Supabase Setup Reference** | [supabase/SETUP.md](../supabase/SETUP.md) | Database schema migrations, environment configuration, and seed utilities. |
| **Legacy Prototypes Reference** | [examples/legacy/README.md](../examples/legacy/README.md) | Documentation for historical prototypes and standalone CLI scripts. |
