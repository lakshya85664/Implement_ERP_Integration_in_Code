# ERP Workflow State Diagram

```mermaid
stateDiagram-v2
    [*] --> created
    created --> running: start
    running --> completed: complete
    running --> waiting: pause
    waiting --> running: resume
    running --> needs_review: fail
    completed --> [*]
    needs_review --> [*]