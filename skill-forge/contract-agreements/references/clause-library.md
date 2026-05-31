# Clause Library — Reusable Contract Provisions

> **Last verified:** 2026-05-28. Adapt to context — don't copy blindly.
> These are starting points, not final language.
> Reference: CaseMark settlement-agreement skill (github.com/CaseMark/skills) for
> US-litigation-grade settlement structure. Adapted for Ontario context here.

## Document Title Convention

| Use case | Title |
|---|---|
| Standard settlement | **Settlement Agreement and Mutual Release** |
| Settlement + IP transfer | **Settlement Agreement and Mutual Release** (IP assignment as term, not title) |
| Standalone IP assignment | **IP Assignment Agreement** |
| Service contract | **Service Agreement** or **Independent Contractor Agreement** |
| No ongoing obligations | **Full and Final Settlement Agreement** |

The title should reflect the document's primary legal effect. If the core purpose is
releasing claims, "Mutual Release" belongs in the title. IP assignment is a term
*within* the settlement, not the document's reason for existing.

---

## Payment Clauses

### Fixed payment, due on condition
```
The Client shall pay the Developer $[AMOUNT] CAD (the "Settlement Amount") by
wire transfer or electronic funds transfer within [N] business days of the later of:
  (a) the Client's written confirmation that the [deliverable/services] meet the
      Acceptance Criteria (Section [X]); or
  (b) the execution of this Agreement by both Parties.
```

### Late payment / interest
```
Any amounts not paid when due shall bear interest at the rate of [X]% per annum
(simple interest), or the rate prescribed under s. 128 of the Courts of Justice Act
(Ontario), whichever is higher. Interest shall accrue from the due date until payment.
```

### Payment schedule (project-based)
```
The Client shall pay the Developer as follows:

  [ ] $[AMOUNT] upon execution of this Agreement (deposit)
  [ ] $[AMOUNT] upon delivery of [MILESTONE 1]
  [ ] $[AMOUNT] upon delivery of [MILESTONE 2]
  [ ] $[AMOUNT] upon final acceptance

Each payment is due within [N] days of the triggering event.
```

### Retainer / recurring
```
The Client shall pay a retainer of $[AMOUNT] CAD per [month/week], due on the
[N]th day of each month. The Developer shall invoice monthly for work performed
against the retainer. Any hours exceeding the retainer amount shall be billed at
$[RATE]/hr and due within [N] days of invoice.
```

---

## IP Assignment Clauses

### Full assignment (developer → client)
```
Upon [receipt of the Settlement Amount / full payment], the Developer assigns to the
Client all right, title, and interest in and to the [Work Product], including:

  (a) All source code, design files, images, and content created for the [Work Product];
  (b) Any domain names, subdomains, and hosting configuration relating to the
      [Work Product];
  (c) All trademarks, trade names, and branding developed for the [Work Product];
  (d) All copyright and moral rights, including the right to register such rights,
      in the foregoing.
```

### Portfolio / attribution rights (developer retains)
```
Notwithstanding the assignment in Section [X], the Developer reserves the
non-exclusive right to:
  (a) Display the [Work Product] in the Developer's portfolio and promotional
      materials;
  (b) Attribute the Developer as the creator of the [Work Product];
  (c) Use the underlying skills, techniques, and methodologies (but not the
      Client's confidential information) in future projects.
```

### No assignment until paid
```
The Developer retains all rights, title, and interest in the Work Product until
full payment of all amounts due under this Agreement. No assignment or license
is effective until payment is received and cleared.
```

---

## Mutual Release Clauses

### Full mutual release
```
Subject to the payment and assignment provisions of this Agreement, each Party
releases the other from all claims, demands, and causes of action arising out of
or relating to [SUBJECT MATTER], whether known or unknown, up to the date of
this Agreement.
```

### Carve-outs (what is NOT released)
```
This release does not apply to:
  (a) Claims arising from breach of this Agreement;
  (b) Claims for fraud, wilful misconduct, or criminal acts;
  (c) Claims that cannot be waived by law (including statutory limitation periods);
  (d) Rights under the Limitations Act, 2002 that have not yet accrued.
```

### Mutual release with consideration clause
```
Each Party acknowledges that the mutual promises, releases, and covenants set out
in this Agreement constitute valuable consideration for the other Party's release.
Each Party expressly waives any rights under s. [X] of any statute that would
otherwise limit the effectiveness of this release.
```

---

## Confidentiality / NDA Clauses

### Standard confidentiality
```
Each Party agrees to hold the other's Confidential Information in strict confidence
and not to disclose it to any third party without the other's prior written consent.
"Confidential Information" means all non-public information disclosed in connection
with [SUBJECT MATTER], including business plans, technical data, client lists,
and financial information.
```

### Exclusions from confidentiality
```
Confidential Information does not include information that:
  (a) Is or becomes publicly available through no fault of the receiving Party;
  (b) Was rightfully in the receiving Party's possession before disclosure;
  (c) Is independently developed by the receiving Party without use of the
      disclosing Party's confidential information;
  (d) Is required to be disclosed by law or court order.
```

---

## Termination Clauses

### For convenience (project-based)
```
Either Party may terminate this Agreement upon [N] days' written notice. Upon
termination, the Client shall pay the Developer for all work performed up to the
date of termination, including any non-cancellable expenses incurred.
```

### For cause
```
Either Party may terminate this Agreement immediately upon written notice if:
  (a) The other Party materially breaches this Agreement and fails to cure
      the breach within [N] days of written notice; or
  (b) The other Party becomes insolvent, makes an assignment for the benefit of
      creditors, or ceases to carry on business.
```

---

## Invoice Clauses

### Header / To-From
```
**From:** [Business Name or Individual]
[Address / Contact]

**To:** [Client Name / Business]
[Client Address / Contact]

**Invoice #:** [NUMBER]
**Date:** [DATE]
**Period:** [START — END]
```

### Services rendered (itemized)
```
| # | Description | Quantity | Rate | Amount |
|---|---|---|---|---|
| 1 | [Item description — scope summary, deliverable] | [hours/qty] | $[RATE] | $[AMOUNT] |
| 2 | [Infrastructure / tools / third-party costs] | — | — | $[AMOUNT] |
|   | **Total due** | | | **$[TOTAL]** |
```

### Dual-option payment (full amount + settlement alternative)
```
**Option A — Full amount**
$[FULL_AMOUNT] — total due for all services rendered.

**Option B — Settlement**
$[SETTLEMENT_AMOUNT] — honour the [proposal name/date] terms.
Available for [N] days from this invoice date.

*Note: Option B is a formal Offer to Settle under Rule 19, O. Reg. 258/98 —
double costs may apply if refused.*
```

### Payment instructions
```
**Payment Method:** E-transfer to [EMAIL] / Wire transfer to [BANK]
**Account:** [Details — fill per-instance, never hardcode]
**Due:** [upon receipt / NET15 / NET30]
```

### Late payment / interest (invoice version)
```
Amounts not paid when due shall bear interest at the rate prescribed under
s. 128 of the Courts of Justice Act (Ontario) from the due date until payment.
```

### Invoice footer / disclaimer
```
This invoice covers all work performed during the stated period. A detailed
time record is available on request. No payment for the above services has
been received unless otherwise noted.
```

### Offer to Settle reference (Ontario Rule 19)
```
Option B above is a formal Offer to Settle within the meaning of Rule 19 of
the Ontario Rules of Civil Procedure, O. Reg. 258/98. If the Client does not
accept this offer and a court later awards an amount equal to or less than the
offer, the Developer may be entitled to double costs from the date of the
offer.
```

---

## Change Request Template (Post-Launch Revisions)

Use this for the one revision round included in post-launch support.
Standard format keeps changes batchable and unambiguous:

```
Page URL — what's currently there → what it should say/do

Examples:
  /about — "experience" section lists 3 certifications
    → update to 5, add 2026 cert
  /contact — form says "we'll respond in 48 hours"
    → change to "24 hours"
  /pricing — RMT pricing column missing "60-min session" at $120
    → add it
```

Include in post-launch support section of settlement agreements or
service contracts where a revision round is offered.

---

## Schedule / Exhibit Pattern

When a prior proposal or document is incorporated by reference:

```
Recital B: [description], a copy of which is attached as Schedule A.

---

## Schedule A — [Title]

[Attached: description of document]
```

The schedule should be attached as a separate file (PDF or HTML copy of
the original proposal/email). Reference it in the recitals and attach it
physically to the signed agreement.

---

## General Provisions

### Governing law (Ontario)
```
This Agreement is governed by the laws of Ontario and the federal laws of Canada
applicable therein. The Parties attorn to the exclusive jurisdiction of the courts
of Ontario.
```

### Entire agreement
```
This Agreement constitutes the entire agreement between the Parties concerning
[SUBJECT MATTER] and supersedes all prior discussions, agreements, and
understandings, whether written or oral.
```

### Amendment
```
This Agreement may be amended only by a written document signed by both Parties.
```

### Independent Legal Advice
```
Each Party acknowledges that they have had the opportunity to obtain independent
legal advice before signing this Agreement, or have freely chosen not to do so.
```

### Counterparts
```
This Agreement may be executed in counterparts, including electronic copies, each
of which is deemed an original and all of which together constitute one agreement.
```

### Dispute resolution (multi-step)
```
Any dispute arising out of or relating to this Agreement shall be resolved as follows:
  (a) The Parties shall first attempt to resolve the dispute through good-faith
      negotiation within [N] days;
  (b) If not resolved, the dispute shall be submitted to mediation before a mutually
      agreed mediator;
  (c) If not resolved within [N] days of mediation, either Party may refer the
      dispute to the Ontario Small Claims Court (if within its jurisdiction) or
      to the Ontario Superior Court of Justice.
```
