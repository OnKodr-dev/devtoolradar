---
title: 'Claude API Tutorial: Getting Started in 2026'
description: 'A practical Claude API tutorial for developers. Learn authentication, core endpoints, streaming, tool use, and best practices with real code examples.'
pubDate: '2026-07-22'
heroImage: '/claude-api-tutorial.jpeg'
---

Anthropic's Claude API has matured into one of the most capable large language model APIs available to developers, offering a clean REST interface, generous context windows, and standout performance on reasoning and code generation tasks. Whether you're building a production AI application, prototyping an internal tool, or integrating an LLM into an existing pipeline, getting comfortable with the Claude API is worth your time. This tutorial walks through everything you need to go from zero to a working integration — covering authentication, basic completions, streaming, tool use, and a few production-level considerations that trip up developers early on.

## Prerequisites and Setup

You'll need an Anthropic API key, which you can generate from the [Anthropic Console](https://console.anthropic.com). At the time of writing, new accounts receive free credits to experiment with.

Install the official Python SDK:

```bash
pip install anthropic
```

Or the Node.js SDK:

```bash
npm install @anthropic-ai/sdk
```

Set your API key as an environment variable rather than hardcoding it:

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

The SDK automatically reads `ANTHROPIC_API_KEY` from the environment, so you don't need to pass it explicitly in most cases.

## Making Your First API Call

The primary endpoint is `messages.create`. Unlike the older completions pattern, the Messages API uses a structured conversation format.

```python
import anthropic

client = anthropic.Anthropic()

message = client.messages.create(
    model="claude-opus-4-5",
    max_tokens=1024,
    messages=[
        {"role": "user", "content": "Explain async/await in Python in two paragraphs."}
    ]
)

print(message.content[0].text)
```

A few things worth noting immediately:

- `max_tokens` is **required** — there's no default. This is intentional; it forces you to think about output length.
- `message.content` is a list of content blocks, not a plain string. For text responses, access `message.content[0].text`.
- `model` should match your use case. Claude Opus is the most capable; Haiku is fastest and cheapest for high-throughput tasks.

### System Prompts

The system prompt sets persistent instructions for the entire conversation and lives outside the `messages` array:

```python
message = client.messages.create(
    model="claude-opus-4-5",
    max_tokens=1024,
    system="You are a senior backend engineer. Be concise and prefer idiomatic Python.",
    messages=[
        {"role": "user", "content": "How should I handle database connection pooling?"}
    ]
)
```

System prompts are a first-class parameter in Claude's API — not just a prepended user message — which means they're handled differently in Claude's context window management.

## Multi-Turn Conversations

For conversational applications, you maintain the message history yourself and pass it on each request:

```python
conversation_history = []

def chat(user_message: str) -> str:
    conversation_history.append({"role": "user", "content": user_message})
    
    response = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=1024,
        messages=conversation_history
    )
    
    assistant_reply = response.content[0].text
    conversation_history.append({"role": "assistant", "content": assistant_reply})
    
    return assistant_reply

print(chat("What's the difference between a process and a thread?"))
print(chat("When would I prefer one over the other?"))
```

This stateless design means you own the conversation state, which gives you full control over context window management — you can trim, summarize, or persist history however fits your architecture.

## Streaming Responses

For user-facing applications, streaming dramatically improves perceived performance. The SDK makes this straightforward:

```python
with client.messages.stream(
    model="claude-opus-4-5",
    max_tokens=1024,
    messages=[{"role": "user", "content": "Write a Python function to parse JWT tokens."}]
) as stream:
    for text in stream.text_stream:
        print(text, end="", flush=True)
```

In a FastAPI or Flask application, you'd yield these chunks as server-sent events (SSE). The streaming interface also exposes `stream.get_final_message()` to retrieve the complete response object after the stream finishes, which you'll want for logging token usage.

## Tool Use (Function Calling)

Tool use is where Claude's API starts to feel genuinely powerful. You define tools as JSON schemas, and Claude decides when to invoke them based on the conversation context.

```python
tools = [
    {
        "name": "get_github_stars",
        "description": "Fetch the current star count for a GitHub repository",
        "input_schema": {
            "type": "object",
            "properties": {
                "owner": {"type": "string", "description": "Repository owner"},
                "repo": {"type": "string", "description": "Repository name"}
            },
            "required": ["owner", "repo"]
        }
    }
]

response = client.messages.create(
    model="claude-opus-4-5",
    max_tokens=1024,
    tools=tools,
    messages=[{"role": "user", "content": "How many stars does the anthropics/sdk-python repo have?"}]
)

# Check if Claude wants to call a tool
if response.stop_reason == "tool_use":
    tool_use_block = next(b for b in response.content if b.type == "tool_use")
    tool_input = tool_use_block.input
    # Execute your actual function here, then pass the result back
```

After executing the tool, you append the result to the conversation and call the API again. Claude then synthesizes the tool result into a natural language response. This loop — call API, execute tool, return result, call API again — is the foundation of most agentic workflows.

## Vision: Passing Images

Claude's multimodal capabilities accept images as base64-encoded data or URLs:

```python
import base64

with open("architecture_diagram.png", "rb") as f:
    image_data = base64.standard_b64encode(f.read()).decode("utf-8")

message = client.messages.create(
    model="claude-opus-4-5",
    max_tokens=1024,
    messages=[
        {
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {"type": "base64", "media_type": "image/png", "data": image_data}
                },
                {"type": "text", "text": "Identify any potential bottlenecks in this architecture."}
            ]
        }
    ]
)
```

This is particularly useful for code review tools that process screenshots, diagram analyzers, or document processing pipelines.

## Key Considerations for Production

### Token Management and Cost Control

Monitor your token usage via `response.usage`. For cost-sensitive applications, Claude Haiku handles routine tasks at a fraction of Opus pricing. A practical pattern is routing: classify the request complexity first, then dispatch to the appropriate model tier.

### Rate Limits and Retries

Anthropic enforces rate limits at the token-per-minute and requests-per-minute level. The SDK includes automatic retry logic with exponential backoff for 529 (overloaded) errors, but you should handle `anthropic.RateLimitError` explicitly in production:

```python
from anthropic import RateLimitError
import time

def resilient_call(messages, retries=3):
    for attempt in range(retries):
        try:
            return client.messages.create(
                model="claude-haiku-4-5",
                max_tokens=512,
                messages=messages
            )
        except RateLimitError:
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
            else:
                raise
```

### Context Window Usage

Claude's models support large context windows (up to 200K tokens on Opus), but cost scales with input tokens. For document Q&A scenarios, implement a retrieval step to pass only relevant chunks rather than entire documents.

## Comparing Claude to OpenAI's API

If you're migrating from the OpenAI API, the Claude API is similar enough to feel familiar. Key differences: `max_tokens` is required (vs. optional), the system prompt is a top-level parameter (vs. a message with role "system"), and response content is a typed list of blocks rather than a plain string. Claude's tool use schema is also slightly more explicit about input schemas. Neither is objectively easier — it's mostly a matter of what you've already scaffolded.

## Conclusion

The Claude API is well-designed, well-documented, and straightforward to integrate. For most developers, the path forward is: start with basic `messages.create` calls using Haiku for fast/cheap iteration, add streaming for any user-facing feature, and layer in tool use once you understand how the result loop works. The model itself — especially Opus — performs exceptionally well on complex reasoning and code tasks, which is where you'll notice the quality difference versus other providers. Start with the free credits, build something small, and measure before committing to a model tier for production workloads.