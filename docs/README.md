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

---

## Component & Specialized Documentation

| Document | Location | Description |
| :--- | :--- | :--- |
| **Conversational Intent Classifier** | [backend/docs/conversational_intent_classifier.md](../backend/docs/conversational_intent_classifier.md) | Rule-based regex/keyword intent classification specification. |
| **Conversational Response Policy** | [backend/docs/conversational_response_policy.md](../backend/docs/conversational_response_policy.md) | Deterministic routing decision, safety boundaries, and engine handoff specification. |
| **Prompt Dataset Draft** | [docs/research/conversational_prompt_dataset_draft.md](research/conversational_prompt_dataset_draft.md) | Research draft and labeled evaluation prompts for conversational intents. |
| **Course Dataset Dictionary** | [data/data_dictionary.md](../data/data_dictionary.md) | Field definitions and metadata for `data/FAU_Courses.xlsx`. |
| **Supabase Setup Reference** | [supabase/SETUP.md](../supabase/SETUP.md) | Database schema migrations, environment configuration, and seed utilities. |
| **Legacy Prototypes Reference** | [examples/legacy/README.md](../examples/legacy/README.md) | Documentation for historical prototypes and standalone CLI scripts. |
