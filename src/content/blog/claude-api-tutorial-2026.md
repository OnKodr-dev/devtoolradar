---
title: 'Claude API Tutorial: A Developer's Complete Guide'
description: 'Learn how to integrate the Claude API into your applications. This hands-on tutorial covers authentication, API calls, streaming, and best practices for developers.'
pubDate: '2026-09-30'
heroImage: '/claude-api-tutorial.jpeg'
---

Anthropic's Claude API has emerged as one of the most capable large language model APIs available to developers today. With its 200K context window, strong instruction-following, and thoughtful safety defaults, Claude is increasingly the go-to choice for teams building production AI features — from document analysis pipelines to complex multi-turn agents. This tutorial walks you through everything you need to hit the ground running: authentication, making your first API call, handling streaming responses, managing conversation context, and optimizing for cost and performance.

## Getting Started: Authentication and Setup

Before writing any code, grab your API key from the [Anthropic Console](https://console.anthropic.com). Once you have it, install the official Python or TypeScript SDK:

```bash
# Python
pip install anthropic

# Node.js / TypeScript
npm install @anthropic-ai/sdk
```

Never hardcode your API key. Use environment variables:

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

The SDK automatically reads `ANTHROPIC_API_KEY` from your environment, so initialization is clean:

```python
import anthropic

client = anthropic.Anthropic()
```

```typescript
import Anthropic from '@anthropic-ai/sdk';

const client = new Anthropic();
```

## Making Your First API Call

The core endpoint is `messages.create`. Here's the minimal working example in Python:

```python
import anthropic

client = anthropic.Anthropic()

message = client.messages.create(
    model="claude-opus-4-5",
    max_tokens=1024,
    messages=[
        {"role": "user", "content": "Explain the difference between TCP and UDP in two sentences."}
    ]
)

print(message.content[0].text)
```

A few things to note about the response object:
- `message.content` is a list of content blocks (text, tool_use, etc.)
- `message.usage` gives you input and output token counts for cost tracking
- `message.stop_reason` tells you why generation stopped (`end_turn`, `max_tokens`, `tool_use`)

### Choosing the Right Model

Anthropic offers several model tiers. As of 2026, the main options are:

| Model | Best For | Relative Cost |
|---|---|---|
| `claude-opus-4-5` | Complex reasoning, nuanced tasks | Highest |
| `claude-sonnet-4-5` | Balanced performance/cost | Medium |
| `claude-haiku-3-5` | High-throughput, latency-sensitive | Lowest |

For most production applications, Sonnet hits the sweet spot. Reserve Opus for tasks where reasoning quality measurably affects outcomes.

## System Prompts and Conversation Structure

Claude's API uses a structured message format with explicit roles. The `system` parameter sets persistent context that applies to the entire conversation:

```python
response = client.messages.create(
    model="claude-sonnet-4-5",
    max_tokens=2048,
    system="You are a senior backend engineer specializing in distributed systems. Be concise, use technical language, and always provide code examples where relevant.",
    messages=[
        {"role": "user", "content": "What's the best strategy for handling idempotency in REST APIs?"}
    ]
)
```

### Building Multi-Turn Conversations

The API is stateless — you must send the full conversation history each time. This is by design and gives you complete control:

```python
conversation_history = []

def chat(user_message: str) -> str:
    conversation_history.append({"role": "user", "content": user_message})
    
    response = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=1024,
        system="You are a helpful coding assistant.",
        messages=conversation_history
    )
    
    assistant_message = response.content[0].text
    conversation_history.append({"role": "assistant", "content": assistant_message})
    
    return assistant_message

print(chat("Write a Python function to flatten a nested list"))
print(chat("Now add type hints and a docstring to it"))
```

Managing history length is important — monitor token counts and implement a windowing strategy (e.g., keep the last N turns, or summarize older context) before you approach the context limit.

## Streaming Responses

For any user-facing application, streaming dramatically improves perceived performance. The SDK makes this straightforward:

```python
with client.messages.stream(
    model="claude-sonnet-4-5",
    max_tokens=1024,
    messages=[{"role": "user", "content": "Explain async/await in Python with examples"}]
) as stream:
    for text in stream.text_stream:
        print(text, end="", flush=True)
```

In a web context, you'd typically pipe this through Server-Sent Events (SSE) or WebSockets. Here's a FastAPI example:

```python
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
import anthropic

app = FastAPI()
client = anthropic.Anthropic()

@app.post("/chat")
async def chat_stream(prompt: str):
    def generate():
        with client.messages.stream(
            model="claude-sonnet-4-5",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}]
        ) as stream:
            for text in stream.text_stream:
                yield f"data: {text}\n\n"
    
    return StreamingResponse(generate(), media_type="text/event-stream")
```

## Tool Use (Function Calling)

Claude's tool use lets you build reliable AI agents that interact with external systems. Define tools using JSON Schema:

```python
tools = [
    {
        "name": "get_stock_price",
        "description": "Retrieves the current stock price for a given ticker symbol",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {
                    "type": "string",
                    "description": "Stock ticker symbol (e.g., AAPL, GOOGL)"
                }
            },
            "required": ["ticker"]
        }
    }
]

response = client.messages.create(
    model="claude-sonnet-4-5",
    max_tokens=1024,
    tools=tools,
    messages=[{"role": "user", "content": "What's the current price of Apple stock?"}]
)

if response.stop_reason == "tool_use":
    tool_block = next(b for b in response.content if b.type == "tool_use")
    print(f"Claude wants to call: {tool_block.name}")
    print(f"With inputs: {tool_block.input}")
```

After executing the tool, send results back in a `tool_result` message to continue the conversation. This pattern is the backbone of most agentic workflows.

## Cost Optimization and Best Practices

### Prompt Caching

If you're sending the same large context repeatedly (e.g., a long system prompt or reference document), use prompt caching to dramatically reduce costs:

```python
response = client.messages.create(
    model="claude-sonnet-4-5",
    max_tokens=1024,
    system=[
        {
            "type": "text",
            "text": very_long_system_prompt,
            "cache_control": {"type": "ephemeral"}
        }
    ],
    messages=[{"role": "user", "content": user_query}]
)
```

Cached tokens are billed at roughly 10% of the standard input token price — a significant saving for document Q&A or RAG-style applications.

### Error Handling

Always handle rate limits and API errors gracefully:

```python
from anthropic import RateLimitError, APIStatusError
import time

def resilient_completion(messages, retries=3):
    for attempt in range(retries):
        try:
            return client.messages.create(
                model="claude-sonnet-4-5",
                max_tokens=1024,
                messages=messages
            )
        except RateLimitError:
            wait = 2 ** attempt
            print(f"Rate limited. Waiting {wait}s...")
            time.sleep(wait)
        except APIStatusError as e:
            if e.status_code >= 500:
                time.sleep(2 ** attempt)
            else:
                raise
    raise Exception("Max retries exceeded")
```

### Token Counting

Use the `count_tokens` endpoint before expensive calls to validate your context fits within limits and estimate costs without consuming tokens.

## Conclusion

The Claude API is well-documented, the SDK is ergonomic, and features like prompt caching and tool use make it genuinely production-ready. The stateless message format feels verbose initially, but it gives you fine-grained control over conversation context — a worthwhile tradeoff for production systems.

**Where to go from here:** If you're building document-heavy applications, explore the Files API and multimodal inputs. For agent workflows, dig into multi-step tool use with parallel tool execution. And if you're running high-volume workloads, the Batches API can cut costs by 50% for async jobs.

Start with Sonnet, instrument your token usage from day one, and reach for Opus only when you have evidence that it moves the needle on quality.