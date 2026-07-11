---
id: doc-metadata-template
title: Documentation Metadata Template
type: template
tags: [template, metadata, docs, ai]
keywords: [frontmatter, yaml, title, id, tags, keywords, summary, ai-readable]
summary: Reusable frontmatter template for any documentation file in this repository so AI tools can read consistent metadata before the content.
---

# Documentation Metadata Template

Use this at the top of every new doc. Keep the YAML frontmatter exactly at the top so tools can parse it before reading the body.

## Recommended fields

- `id`: stable machine-friendly identifier
- `title`: human-friendly doc title
- `type`: overview, architecture, setup, guide, reference, template, etc.
- `tags`: short labels for grouping
- `keywords`: AI/search-friendly terms
- `summary`: one-paragraph description of what the doc covers

## Example

```md
---
id: project-overview
title: Naruto Card Clash - Project Overview
type: project
tags: [naruto, overview, tech-stack, frontend, backend]
keywords: [game, card-battle, websocket, stomp, angular, spring-boot]
summary: High-level overview of the Naruto Card Clash 1v1 real-time card-battle game project, including game rules, tech stack, and user flow.
---
```

## Rules

- Keep the frontmatter concise.
- Use lowercase, hyphenated ids.
- Keep the summary to 1-2 sentences.
- If you add a new doc later, copy this structure first.
