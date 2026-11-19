# Product

## Users

AI engineers running LiveKit Agents who need every session's recording,
transcript and evaluation in one durable, inexpensive, S3-compatible store, with a
retention policy they can explain. Their context: they are iterating on a voice
agent, want to replay and score sessions, and do not want a hosted model or
speech provider in the loop for that.

## Product Purpose

A runnable reference for archiving voice-agent sessions on Backblaze B2. A local
LiveKit stack records each session with Egress straight to B2; signed webhooks
and local post-processing keep a per-session manifest that links the recording
(location, size, duration, SHA-256), a faster-whisper transcript and a
deterministic evaluation; a retention job keeps or removes sessions by class and
reports what it did. Success = a developer runs `make up` and `make demo`, sees a
processed session in B2 within a minute, and can adapt the pattern to their own
agent.

## Maturity and Support Boundary

This is a maintained open-source sample, not a complete hosted SaaS product.
It is built with production-minded controls and can be adapted for production use with
caution, but adopters own product-specific validation, security, deployment, and
operations. Repository defects and feature requests go through the public GitHub issue
tracker; B2 account, billing, service, and API questions go through Backblaze Support.
The template/sample itself is not covered by the Backblaze service level agreement,
and no SLA is provided for the repository software.

## Brand Personality

Confident, precise, quietly professional. Voice is direct and free of hype. The
interface should feel like a developer tool for inspecting evidence: calm,
trustworthy, every number traceable to an object in the bucket.

## Anti-references

- **Generic AI/SaaS slop.** No gradient text, hero-metric templates, identical
  icon-card grids, tracked uppercase eyebrows, or decorative glassmorphism.
- **Over-branded / loud.** No heavy brand-color drenching, decorative motion, or flashy
  effects. It is scaffolding to be rebranded, not a hero page.
- **Toy / prototype feel.** No missing states, inconsistent components, or placeholder
  polish. Must read as polished, dependable scaffolding.
- **Enterprise-drab.** No Bootstrap-era gray boxes or dense-but-lifeless admin-panel
  look. Considered, like modern dev tools (Linear, GitHub Primer, Stripe).

## Design Principles

- **Show the evidence.** Every session screen links to the objects in B2 that back
  it: recording key, manifest, transcript, evaluation, webhook evidence.
- **Neutral foundation, easy to rebrand.** Identity lives in tokens (`globals.css`) and
  one config file. Screens are built from the shared UI kit so a rebrand is a token
  swap, not a rewrite.
- **Earned familiarity over novelty.** Use standard, trusted affordances (top bar +
  side nav, command palette, data tables). The tool disappears into the task.
- **Every state is designed.** Default, hover, focus, active, disabled, loading (skeleton),
  empty (teaches the interface), and error (says what's wrong + offers retry) — never
  half-shipped.
- **Consistency is the feature.** One button vocabulary, one form-control set, one icon
  style across every screen. Divergence is a bug.

## Accessibility & Inclusion

Target **WCAG 2.1 AA**. Body text ≥ 4.5:1, large/bold text ≥ 3:1, visible focus
indicators on every interactive element, full keyboard navigation, correct semantic
landmarks and heading order, labelled form controls, and a `prefers-reduced-motion`
alternative for every animation. Full light and dark theme parity.
