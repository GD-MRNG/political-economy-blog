# Political Economy Blog

A personal blog on political economy, built with Jekyll and hosted on GitHub Pages using the [Lagrange](https://github.com/LeNPaul/Lagrange) theme.

## Setup

### Local

```bash
bundle install
jekyll serve
```

Then open `http://localhost:4000`.

## Reading a briefing

Posts live in `_posts/` and are long. The part an agent needs is the executive summary at the top. It is wrapped in HTML comments, which are present in the Markdown file and in the published page source:

```html
<!-- exec-summary-start -->
<!-- preview-start -->
# Executive Summary

**The Global Operating Picture**

...
<!-- exec-summary-end -->
```

Take the text between `<!-- exec-summary-start -->` and `<!-- exec-summary-end -->`. Everything after the end comment is sources and regional intel.

The lead line under the heading depends on the briefing:

- Global: `**The Global Operating Picture**`. The block stops before the first region.
- Singapore: `**The Singapore Operating Picture**`. The block runs through `## WHAT TO WATCH`.
- Technology: `**The Technology Operating Picture**`. The block runs through `## WHAT THIS MEANS`, including the longer headings that start with those words.

`<!-- preview-start -->` is only the homepage excerpt marker. It sits just after the summary start and has no end comment. A few early posts do not have it. Use the executive-summary pair to extract the summary.

## License

None
