#!/usr/bin/env python3
"""Generate a blog article for DevToolRadar using Claude API + Pexels photo."""

import argparse
import os
import re
import sys
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

import anthropic
import requests

BLOG_DIR = Path(__file__).parent.parent / "src" / "content" / "blog"
PUBLIC_DIR = Path(__file__).parent.parent / "public"

SYSTEM_PROMPT = """You are an expert technical writer for DevToolRadar, a blog focused on AI developer tools.
Write SEO-optimized articles for software developers. Your articles are:
- Practical and actionable, with real-world examples
- Honest and objective, not promotional
- Well-structured with clear headings (##, ###)
- Around 1200 words of body content
- Written in a helpful, professional tone"""


def keyword_to_slug(keyword: str) -> str:
    slug = keyword.lower()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug


def download_pexels_photo(keyword: str, slug: str) -> str | None:
    """Download a relevant photo from Pexels and return the public path."""
    api_key = os.environ.get("PEXELS_API_KEY")
    if not api_key:
        print("Warning: PEXELS_API_KEY not set, skipping photo download.")
        return None

    search_query = keyword.replace("-", " ")
    url = "https://api.pexels.com/v1/search"
    headers = {"Authorization": api_key}
    params = {"query": search_query, "per_page": 5, "orientation": "landscape"}

    try:
        resp = requests.get(url, headers=headers, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        print(f"Warning: Pexels API error: {e}")
        return None

    photos = data.get("photos", [])
    if not photos:
        print(f"Warning: No Pexels photos found for '{keyword}'.")
        return None

    photo = photos[0]
    image_url = photo["src"]["large"]
    ext = image_url.split("?")[0].rsplit(".", 1)[-1] or "jpeg"
    filename = f"{slug}.{ext}"
    filepath = PUBLIC_DIR / filename

    try:
        img_resp = requests.get(image_url, timeout=30)
        img_resp.raise_for_status()
        filepath.write_bytes(img_resp.content)
        print(f"Photo saved: public/{filename}")
        return f"/{filename}"
    except requests.RequestException as e:
        print(f"Warning: Failed to download photo: {e}")
        return None


def generate_article(keyword: str, hero_image: str | None) -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("Error: ANTHROPIC_API_KEY not set.", file=sys.stderr)
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)

    hero_line = f"heroImage: '{hero_image}'" if hero_image else ""

    prompt = f"""Write a complete, SEO-optimized blog article about: "{keyword}"

The article is for DevToolRadar — a blog for software developers covering AI coding tools.

Return the article in this exact format (include the triple-dashes):

---
title: '<SEO title, 50-60 chars, include the keyword>'
description: '<Meta description, 150-160 chars, compelling and keyword-rich>'
pubDate: '{date.today().isoformat()}'
{hero_line}
---

<article body — approximately 1200 words>

Requirements for the article body:
- Start with a strong introduction paragraph (no heading needed)
- Use ## for main sections, ### for subsections
- Include practical examples, comparisons, or use cases
- Cover: what it is, why it matters, key features/considerations, practical guidance
- End with a clear conclusion and recommendation
- Do NOT include the title as an H1 — the frontmatter title handles that
- Write for developers, not beginners — assume coding knowledge"""

    print(f"\nGenerating article for: '{keyword}'...")

    result = []
    with client.messages.stream(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        system=[
            {
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        for text in stream.text_stream:
            print(text, end="", flush=True)
            result.append(text)

    print()
    return "".join(result)


def save_article(content: str, slug: str) -> Path:
    year = date.today().year
    filename = f"{slug}-{year}.md"
    filepath = BLOG_DIR / filename

    if filepath.exists():
        print(f"Warning: {filepath.name} already exists, overwriting.")

    filepath.write_text(content, encoding="utf-8")
    return filepath


def main():
    parser = argparse.ArgumentParser(description="Generate a DevToolRadar blog article")
    parser.add_argument("keyword", help="Topic/keyword for the article")
    args = parser.parse_args()

    keyword = args.keyword.strip()
    if not keyword:
        print("Error: keyword cannot be empty.", file=sys.stderr)
        sys.exit(1)

    slug = keyword_to_slug(keyword)

    hero_image = download_pexels_photo(keyword, slug)

    content = generate_article(keyword, hero_image)

    if "---" not in content:
        print("\nError: generated content missing frontmatter.", file=sys.stderr)
        sys.exit(1)

    filepath = save_article(content, slug)
    print(f"\nSaved: {filepath}")


if __name__ == "__main__":
    main()
