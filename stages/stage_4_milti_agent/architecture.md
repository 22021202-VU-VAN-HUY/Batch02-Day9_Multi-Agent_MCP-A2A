# Stage 4 Architecture

```mermaid
flowchart TD
    START([START]) --> LAW[analyze_law<br/>Lead legal analysis]
    LAW --> ROUTER{check_routing<br/>Keyword-based Send API}

    ROUTER -->|tax / IRS / thuế| TAX[call_tax_specialist<br/>Tax ReAct agent]
    ROUTER -->|compliance / SEC / SOX / AML| COMPLIANCE[call_compliance_specialist<br/>Compliance ReAct agent]
    ROUTER -->|data / privacy / GDPR / dữ liệu| PRIVACY[privacy_agent<br/>Privacy agent]
    ROUTER -->|No specialist needed| AGGREGATE[aggregate]

    TAX --> AGGREGATE
    COMPLIANCE --> AGGREGATE
    PRIVACY --> AGGREGATE
    AGGREGATE --> END([END])
```

## Execution Flow

1. `analyze_law` creates the general legal analysis.
2. `check_routing` inspects the question and returns one or more LangGraph `Send` objects.
3. Tax, compliance, and privacy specialists run in parallel when their keywords match.
4. Each specialist writes to its own reducer-backed state field.
5. `aggregate` combines all available analyses into the final response.

Stage 4 runs every agent in one Python process. Stage 5 preserves the same orchestration idea but moves agents into independent HTTP services using the A2A protocol.
