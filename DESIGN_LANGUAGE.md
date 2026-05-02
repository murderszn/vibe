# OpenTutor Design Language

This document defines the visual and editorial rules for OpenTutor and Vibe pages. The goal is a calm academic presentation: serious, readable, parent-led, and transparent.

## Theme

OpenTutor should read like an academic white paper with practical implementation notes. It should not feel like a SaaS landing page, a startup pitch deck, or a colorful app dashboard.

Use this standard:

- Quiet
- Scholarly
- Structured
- Parent-supervised
- Practical
- Transparent

Avoid this standard:

- Bright accent text
- Decorative gradients
- Promotional subtitles
- Excessive badges
- Dense grids of technical cards
- Marketing language

## Color

Use a neutral academic palette.

- Background: soft off-white or light slate
- Surface: white
- Text: dark slate
- Secondary text: slate gray
- Borders: light slate
- Accent: only neutral slate, never saturated blue, green, amber, or violet

Rules:

- Do not use colorful text for section labels, badges, metadata, or category markers.
- Do not use color as the main way to signal importance.
- Use weight, spacing, borders, and hierarchy instead.
- Links may use the standard dark slate link color, but should not become bright blue unless required by a platform style.

## Typography

Use typography to make the page feel academic.

- Serif headings are appropriate for major section titles.
- Sans-serif body text should stay readable and restrained.
- Avoid oversized subtitles.
- Avoid heavy letter spacing except for very small utility labels.
- Avoid all-caps labels unless they are required for navigation or compact metadata.

Preferred hierarchy:

- H1: document title
- H2: major argument or section
- H3: supporting idea
- Paragraph: primary explanation
- Small label: optional, neutral, and used sparingly

## Section Structure

Sections should explain one idea at a time.

Preferred section format:

1. Heading
2. One short academic framing paragraph
3. Supporting evidence, workflow, diagram, table, or example

Avoid stacking multiple subtitles under every heading. If a second paragraph is needed, write it as body copy, not as a decorative subtitle.

## Components

Cards are allowed when they group concrete information, but they should be restrained.

Use cards for:

- Repeated items
- Examples
- Implementation notes
- Comparisons
- Resources

Avoid cards for:

- Every sentence
- Decorative section wrappers
- Pure marketing claims

Badges and labels:

- Use sparingly
- Keep neutral
- Prefer title case
- Avoid saturated colors
- Avoid all-caps styling unless the label is very short and functional

## Voice

Write like a serious project note for parents, students, and builders.

Use:

- Clear explanation
- Concrete nouns
- Plain verbs
- Specific workflows
- Human supervision language

Avoid:

- Hype
- Buzzwords without explanation
- Vague claims
- Overly technical implementation detail in public-facing sections

## Vibe Presentation

Vibe should be described as:

- A classroom tutor
- A family helper
- A repo guide
- A live-information assistant
- A tool inside a parent-operated system

Vibe should not be framed as:

- An autonomous school operator
- A replacement for parents
- A moderation or server administration system
- A generic chatbot

## Current Site Rules

For `site/index.html`:

- Keep the `Vibe + Tutor` section combined.
- Keep the palette neutral.
- Do not add colorful category text.
- Do not add extra subtitle paragraphs unless they clarify the argument.
- Prefer fewer panels with stronger explanations over many small boxes.
- Use prompt examples only when they show real family workflows.
