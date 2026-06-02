---
name: contract-agreements
description: |
  Draft Ontario/Canadian legal agreements, settlements, IP assignments, and service contracts for developer-to-client arrangements. Use this skill whenever the user mentions contracts, agreements, settlements, terms, legal documents, IP assignment, mutual release, NDA, service agreement, freelance contract, or any kind of legal writing between parties. Covers: settlement agreements, IP assignment, mutual release, service agreements, payment terms, NDAs, and consulting agreements. ALWAYS includes lawyer-review disclaimer. NOT for litigation strategy, court filings, or legal advice — only document drafting.
metadata:
  author: curtismercier/gravicity
  version: "1.1.0"
  source-style: authored
  home-repo: curtismercier/skill-forge/skill-forge/contract-agreements
  created: 2026-05-27
  last_reviewed: 2026-06-01
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
- Invoices (demand for payment, itemized billing, full + settlement dual-option)

**What it does NOT cover:**
- Court filings, litigation strategy, or legal advice
- Bookkeeping, accounting, or tax advice (invoices are billing documents, not financial records)
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

Every document (agreements/contracts) follows this structure:

```markdown
⚠️ DISCLAIMER: This is a template for reference purposes only. Have it reviewed
by a qualified Ontario-licensed attorney before signing.

# [DOCUMENT TYPE — ALL CAPS]

**DRAFT — FOR REVIEW** (only if pre-signature draft)

This [Document Type] (the "Agreement") is made as of ___________________, [YEAR]
(the "Effective Date") by and between:

**[Party A Name]**, [description / carrying on business as] ("[Short Name A]")

— and —

**[Party B Name]**, [description / carrying on business as] ("[Short Name B]")

Each referred to as a "Party" and collectively as the "Parties."

---

## Recitals

A. [Factual context]
B. [Prior relationship / work performed]
C. [Reason for this document]

**NOW, THEREFORE**, in consideration of the mutual promises, covenants, and releases
contained in this Agreement, and for other good and valuable consideration, the receipt
and sufficiency of which is hereby acknowledged, the Parties agree as follows:

---

## 1. [Section Title]

[Terms ...]

## N. General Provisions

N.1 **Governing Law.** This agreement is governed by the laws of Ontario
    and the federal laws of Canada applicable therein.
N.2 **Entire Agreement.** ...
N.3 **Amendment.** ...
N.4 **Counterparts.** ...
N.5 **Independent Legal Advice.** Each Party acknowledges that they have
    had the opportunity to obtain independent legal advice.

---

## Signatures

**[PARTY A NAME] ([Short Name A])**

Signature: _______________________________

Name: [Printed]

Date: __________________

---

**[PARTY B NAME] ([Short Name B])**

Signature: _______________________________

Name: [Printed]

Date: __________________

---

*DRAFT v[VERSION] — [DATE]. Prepared by [Drafter]. Not a legally binding document
until signed by both Parties.*
```

**Key formatting conventions:**
- Title in ALL CAPS for legal document headings
- Opening clause: "This Agreement is made as of [Date] by and between:"
- Party separator: "— and —" on its own line
- Defined terms in quotes on first use: ("Developer")
- "Effective Date" as defined term at the top
- "NOW, THEREFORE" closes recitals with standard consideration language
- Section numbers use 1., 1.1, 1.2 format throughout
- Signature blocks include full party name, signature line, printed name, date

### Settlement agreement specifics

Include these sections in addition to the general structure:

| Section | What it covers |
|---|---|
| Settlement Payment | Amount, due date, payment method, timing trigger, late-payment acceleration |
| IP Assignment | What is being transferred, effective on payment |
| Acceptance / Verification | Review period, defect remedy process, acceptance criteria |
| Post-Delivery Support | Support period, bug-fix warranty, **access-conditional** (see pattern below) |
| Mutual Release | Both parties release claims (subject to exceptions), known + unknown claims |
| Confidentiality / Non-Disparagement | Terms confidentiality, no negative statements |
| Representations | Each party's warranties (authority, ownership, etc.) |

#### Access-conditional warranty pattern

When the Developer provides post-delivery support or a bug-fix warranty, it is
standard practice to condition those obligations on the Developer retaining access
to the deliverables. Use this clause pattern:

```
The Developer's obligations under [Section X] are expressly conditional on the
Developer retaining the following access throughout the applicable period:
  (a) Read/write access to the GitHub repository containing the [deliverable];
  (b) Access to the [shared account / hosting platform] set up for the project.

If any of the above access rights are revoked, restricted, or otherwise made
unavailable to the Developer at any time during the support or warranty period,
the Developer's obligations shall immediately and automatically terminate. The
Developer shall not be required to request or re-request access.
```

This protects against the common scenario where a client revokes access during
the warranty period, then demands support — the developer should not be on the
hook for issues they can't access or reproduce.

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

### Invoice specifics

Invoices are billing documents — they itemize work performed and demand payment.
Unlike agreements, they are not signed by both parties. They can include optional
settlement offers (Path A-style dual-option) as an alternative to the full amount.

| Section | What it covers |
|---|---|
| Header | From (business/individual), To (client), invoice #, date, period covered |
| Services Rendered | Itemized list with description, quantity (hours), rate, amount |
| Total | Clear total due, optionally with currency stated |
| Payment Options (optional) | Alternative settlement path with expiry date (e.g., "$3,500 if paid within 14 days") |
| Payment Terms | Due date, accepted methods (e-transfer, wire, cheque), late payment interest |
| Legal Footer | Offer to Settle under Rule 19 (if applicable), s.128 interest notice, disclaimer |
| Notes | Contextual references to prior correspondence, quotes from client messages |

**Key differences from agreements:**
- Unilateral (from issuer) — no signature block needed
- Always includes REMIT-TO (payment destination) — bank details or e-transfer address
- Settlement/dual-option structure is a demand with a carrot, not a negotiated compromise
- References to prior communication (quotes, email excerpts) can establish the timeline

**Rendering:** The same `render-agreement.py` script works for invoices — it converts
markdown to editable HTML with the same inline-edit + print-to-PDF workflow.

*Example in practice: Invoice 2026-05-19-ARZ-001 (handoff matter) — full HTML invoice
with dual-option payment structure, embedded client quotes, and Offer to Settle language.*

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
- **Don't add signature blocks to invoices** — they're billing documents, not agreements
- **Don't embed bank details in the template** — use [bank details to be provided] in templates; fill when sending
- **Don't tie a release or demand withdrawal to the signing date** — always tie it to receipt of payment (see clause-library: Release on Payment)
- **Don't settle for less than full value without a default reinstatement clause** — prevents the settlement from becoming a free option (see clause-library: Default Reinstatement)
- **Don't let the cover email promise more than the agreement contains** — Section 11.2 (Entire Agreement) wipes email promises; everything must be in the binding document
- **Don't use "without prejudice" when the facts favor you** — an open letter is fully admissible and signals confidence (see Strategic Considerations below)

## Strategic considerations (added 2026-06-01)

### Open letter vs. without prejudice
- **Open letter**: Fully admissible in court. Use when the documented facts strongly favor your position. Signals confidence, puts the other side on notice.
- **Without prejudice**: Protected from admissibility. Use when you're exploring compromise or your position has weaknesses.
- **Without prejudice except as to costs**: Only usable for costs arguments under Rule 14.07. Middle ground — protects the substance but preserves the costs lever.

### Settlement agreement structural safeguards
Three clauses that should be standard in any below-value settlement:
1. **Release on payment** (not signing) — never give up leverage before receiving consideration
2. **Default reinstatement** — if payment defaults, the original claim survives at full value
3. **As-is delivery + separate warranty option** — withdraw unworkable warranty terms without appearing unreasonable

All three are templated in `references/clause-library.md`.
