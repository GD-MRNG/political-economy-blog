# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
bundle install       # install Ruby dependencies
jekyll serve         # serve locally at http://localhost:4000
```

GitHub Pages builds and deploys automatically on every push to `main`.

## Architecture

Jekyll blog using the [Lagrange](https://github.com/LeNPaul/Lagrange) theme, hosted at `https://gd-mrng.github.io/political-economy-blog/`.

Key config in `_config.yml`:
- `permalink: /:categories/:year/:month/:day/:title.html`
- `paginate: 20`
- Plugins: `jekyll-paginate`, `jekyll-sitemap`, `jekyll-feed`, `jekyll-seo-tag`

Site navigation and social links are configured in `_data/settings.yml`.

## Posts

All posts live in `_posts/` with filenames `YYYY-MM-DD-Title.md`. The filename slug becomes the `:title` URL segment — it is independent of the `title:` front matter field.

Required front matter for all briefing posts:

```yaml
---
layout: post
title: "🌏 Global Briefing | 11 May 2026"
author: "Glenn Lum"
date: 2026-05-11 08:00:00 +0800
categories: weekly briefing
tags: [global]          # use: global | sg | tech
---
```

`categories: weekly briefing` (two words) generates the `/weekly/briefing/` URL prefix. All three briefing types (Global, Singapore, Technology) use this same category.

## Automation Scripts

`scripts/batch_post_generator.py` — generates post stub files from a pipe-delimited `scripts/manifest.txt`:
```
title | date | image | [tags]
```

`scripts/manifest_builder.py` — interactive CLI to build manifest entries before running the generator.

Auto-published posts are committed directly with the message pattern `Auto-Publish: [Briefing Type]`.
