# Question Policy

PromptGate should minimize friction.

Ask a clarifying question only when all of these are true:

1. The missing information materially changes the downstream task.
2. A reasonable assumption would likely produce the wrong result.
3. The request cannot be safely refined without that information.

When asking, ask exactly one question.

Do not ask just to make the prompt more polished. If the user intent is clear enough, refine and continue.

## Examples

No question:

```text
이거 별론데 코드말고 방향만
```

Reason: The user wants direction without code. The target artifact may be implicit, but the exclusion and output preference are clear enough.

One question:

```text
이거 정리해서 보내줘
```

Reason: If there is no visible artifact or recipient context, the downstream output could be an email, report, chat message, or summary. Ask what artifact should be refined.
