---
name: contract-agreements
description: |
  Draft Ontario/Canadian legal agreements, settlements, IP assignments, and service contracts for developer-to-client arrangements. Use this skill whenever the user mentions contracts, agreements, settlements, terms, legal documents, IP assignment, mutual release, NDA, service agreement, freelance contract, or any kind of legal writing between parties. Covers: settlement agreements, IP assignment, mutual release, service agreements, payment terms, NDAs, and consulting agreements. ALWAYS includes lawyer-review disclaimer. NOT for litigation strategy, court filings, or legal advice — only document drafting.
metadata:
  author: curtismercier/gravicity
  version: "1.0.0"
  source-style: authored
  home-repo: curtismercier/skill-forge/skill-forge/contract-agreements
  created: 2026-05-27
  last_reviewed: 2026-05-27
  review_interval_days: 180
---

# contract-agreements

Draft Ontario-law legal agreements for developer-client arrangements. Produces structured documents that cover parties, recitals, terms, signatures, and include appropriate legal-review disclaimers.

## When to use this skill

**Trigger words:** contract, agreement, settlement, terms, legal, IP assignment, mutual release, NDA, service agreement, freelance, consulting agreement, payment terms, dispute, release.

**What it covers:**
- Settlement agreements (payment + mutual release)
- IP assignment agreements (developer → client asset transfer)
- Service/freelance contracts (scope, payment, IP, termination)
- Mutual release / full and final settlement
- Payment terms and invoicing
- NDA / confidentiality agreements
- Consulting agreements (hourly or project-based)

**What it does NOT cover:**
- Court filings, litigation strategy, or legal advice
- Employment agreements (employee vs contractor distinction)
- Partnership / joint venture / operating agreements (different domain)
- Anything requiring notarization or court filing
- US-specific law (this skill targets Ontario/Canada)

## Core pattern

1. **Identify the type** — settlement, IP assignment, service contract, NDA, etc.
2. **Gather facts** — parties, amount (if any), scope, timeline, governing law
3. **Check references** — `references/ontario-law.md` for statute citations, `references/caselaw.md` for key decisions
4. **Draft with structure** — parties → recitals → terms → signatures → disclaimer
5. **Review** — verify all placeholders filled, Ontario law consistent, disclaimer present

## Output format

Every document follows this structure:

```markdown
⚠️ DISCLAIMER: This is a template for reference purposes only. Have it reviewed
by a qualified Ontario-licensed attorney before signing.

# [DOCUMENT TYPE]

**Date:** [Date]
**Governing Law:** Ontario, Canada
**Prepared by:** [Drafter name/role]

## PARTIES

- **[Party A Name]** ("[Short Name A]")
- **[Party B Name]** ("[Short Name B]")

## RECITALS (Background)

A. [Factual context]
B. [Prior relationship / work performed]
C. [Reason for this document]

## TERMS

### 1. [Section Title]

[Terms ...]

### 2. [Next Section]

[Terms ...]

### N. GENERAL PROVISIONS

N.1 **Governing Law.** This agreement is governed by the laws of Ontario
    and the federal laws of Canada applicable therein.
N.2 **Entire Agreement.** ...
N.3 **Amendment.** ...
N.4 **Counterparts.** ...
N.5 **Independent Legal Advice.** Each Party acknowledges that they have
    had the opportunity to obtain independent legal advice.

## SIGNATURES

**PARTY A:**
Signature: _____________
Name: [Printed]
Date: _________

**PARTY B:**
Signature: _____________
Name: [Printed]
Date: _________
```

### Settlement agreement specifics

Include these sections in addition to the general structure:

| Section | What it covers |
|---|---|
| Settlement Payment | Amount, due date, payment method, timing trigger |
| IP Assignment | What is being transferred, effective on payment |
| Acceptance / Verification | Review period, defect remedy process |
| Mutual Release | Both parties release claims (subject to exceptions) |
| Representations | Each party's warranties (authority, ownership, etc.) |

### IP Assignment Agreement specifics

| Section | What it covers |
|---|---|
| Assignment | Clear statement of what IP is transferred (source code, design, content, domain, branding) |
| Consideration | Payment or other value exchanged for the assignment |
| Representations | Warranties of original authorship, right to assign |
| Reserved Rights | Any rights the developer keeps (portfolio use, license to show work) |

### Service Contract specifics

| Section | What it covers |
|---|---|
| Services | Scope description (can reference SOW or proposal) |
| Compensation | Amount, rate, payment schedule, late payment terms |
| Timeline | Milestones, delivery dates, acceptance periods |
| IP Ownership | Who owns work product (work-for-hire / assignment language) |
| Confidentiality | Protection of proprietary information |
| Termination | Notice periods, kill fees, surviving obligations |
| Liability | Limitation of liability, indemnification |

## Disclaimers required

**Every document MUST include** at the top:
> ⚠️ DISCLAIMER: This is a template for reference purposes only. Have it reviewed by a qualified Ontario-licensed attorney before signing.

If there is a payment or IP transfer involved, also add near payment:
> The developer should retain copies of all work product until full payment is received and cleared.

## Key references

- `references/ontario-law.md` — Ontario statutes (Courts of Justice Act, Limitations Act, etc.)
- `references/caselaw.md` — Key Ontario/Canadian caselaw with CanLII links
- `references/clause-library.md` — Reusable clause templates
- External: `CaseMark/skills` ([GitHub](https://github.com/CaseMark/skills)) — professionally drafted settlement agreement skill (US litigation, adapt for Ontario)

## Scripts available

### render-agreement.py — preview, edit, and save agreements in the browser

Converts a markdown agreement file into a standalone HTML page with:
- Professional contract typography (Georgia serif, print-friendly layout)
- **Inline editing** — each section is contenteditable, click to edit
- **Save button** — downloads edited content as a markdown file
- **Print / PDF button** — native browser print-to-PDF with clean print styles
- Draft watermark, signature blocks, table support

```bash
# Render and open in browser
python3 scripts/render-agreement.py path/to/agreement.md --open

# Render to custom output path
python3 scripts/render-agreement.py path/to/agreement.md --output out.html

# Just generate HTML without opening
python3 scripts/render-agreement.py path/to/agreement.md
```

**Workflow:** Draft agreement in markdown → render to HTML → preview in browser → edit inline → save changes → print to PDF.

## Verification

Last audited: 2026-05-27. When using this skill after a long gap, check:
- Are Ontario statutes still current? (Limitations Act amendments, etc.)
- Has any referenced caselaw been overturned?
- Is the legal-review disclaimer still appropriate for Ontario?
- Does `scripts/render-agreement.py` still work with current Python? (spot-check)

## Pre-push checklist

Before pushing skill changes to a public repo:

- [ ] `grep -in "client\|company\|personal\|name\|specific" scripts/*.py references/*.md` — catch any hardcoded personal info
- [ ] Check signature blocks for real names vs. placeholders
- [ ] `git diff --cached` — review every line for PII before committing
- [ ] If PII snuck in: `git reset --soft HEAD~N` + recommit (don't leave it in history)

## Anti-patterns

- **Don't include payment terms without also including a late-payment / interest clause** (Ontario's Courts of Justice Act s.128 sets the default rate)
- **Don't omit mutual release exceptions** — standard carve-outs for fraud, existing IP, and post-agreement breaches
- **Don't write IP assignment as "all rights" without listing what "all rights" includes** — specificity prevents disputes
- **Don't skip the Independent Legal Advice clause** when the document involves a settlement or release
- **Don't use US-specific terms** (e.g., "small claims court" should reference Ontario Small Claims Court, "Tort law" should reference Ontario's)
