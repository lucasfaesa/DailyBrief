---
title: "Decision: Primary Gemini with Groq Fallback"
type: decision
updated_at: 2026-10-11
---

# Decision — LLM Providers

## Context

The processing pipeline requires LLM capacity to categorize news and extract factual summaries on a scheduled basis, running within GitHub Actions without hosting costs.

## Decision

Adopt **Google Gemini** (`gemini-2.0-flash`) as the primary inference engine and **Groq** (`llama-3.3-70b-versatile`) as the secondary fallback.

## Justifications

- **Free Tier Availability**: Both providers offer generous free usage limits without upfront credit card requirements.
- **Provider Redundancy**: Distinct infrastructure stacks minimize probability of concurrent outages.
- **Latency & Speed**: Both models support high token throughput suited for batch workloads.

## Alternatives Considered

- **OpenAI / Anthropic**: Require billing configurations from initial setup.
- **Self-hosted Ollama**: Contradicts requirement for fully serverless, cloud-based execution.

## Relevant Files

- `src/llm.py`
- `config.yaml`
