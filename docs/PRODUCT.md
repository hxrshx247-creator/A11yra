# A11yra product case

## Pilot and customer

Teachers and TAs distribute course handouts in Word. An unlabeled chart, visual-only heading or generic link can slow down students who use a screen reader, keyboard navigation or magnification. Instructional designers and accessibility staff often help with review. A11yra gives teachers a repeatable way to repair common barriers and verify the result before sharing.

The first pilot targets a single first-year department’s weekly course pack at one local college. Teachers and TAs are daily users. The department head or disability-services office can sponsor a pilot, and the e-learning or IT team can review hosting and data handling. Students are reader users. They need no account for a published link.

**Value proposition** — Find, fix and verify six common document barriers, then give students a reader they control.

## Alternatives and differentiation

| Tool | What it offers | Where A11yra fits |
| --- | --- | --- |
| Microsoft Accessibility Checker and Assistant | Word can identify issues and guide users through repairs. [Microsoft Support](https://support.microsoft.com/en-us/accessibility/office-accessibility/rules-for-the-accessibility-checker) | Test a standalone workflow with workspace audit history and a student-facing HTML reader. |
| Anthology Ally | LMS-integrated feedback and alternative formats for instructors and students. [Ally instructor FAQs](https://help.anthology.com/ally-lms/en/instructors/instructor-faqs-for-ally.html) | Start a small DOCX pilot before an LMS integration or procurement project. |
| PAC | Technical PDF checking, document structure inspection and screen-reader preview. [PAC checks](https://pac.pdf-accessibility.org/en/check) | Focus on editable Word files before distribution. |
| axe-core | Automated checks for web pages and HTML interfaces. [Deque axe-core](https://www.deque.com/axe/axe-core/) | Use axe on A11yra’s own UI and learner export. Word package analysis uses separate checks. |

Accessibility support already exists in the tools teachers use. The pilot tests whether a guided repair, an explicit re-audit and a learner-controlled reader help when a department shares files across different channels. No market size or demand estimate has been validated.

India’s University Grants Commission has published accessibility guidelines for higher education institutions. This gives a college pilot a concrete context for discussing accessibility in teaching workflows. [UGC higher-education accessibility initiative](https://www.ugc.gov.in/KeyInitiative?ID=MNJdt2jZ+aRpA%2FDRRKQwyg%3D%3D)

## Pricing hypothesis and unit economics

Free allows five documents a month and two workspace seats. Educator tests a per-seat monthly subscription for teachers who regularly hit the document or file-size limit. Institution tests a department or site licence for shared workflows with more seats, audit reporting, API access and reader branding. The pilot should ask which budget owns the problem and whether limits match actual usage. Checkout uses Stripe test mode when configured. The app handles no card details.

The local synthetic audit benchmark completed **10 of 10** requests for a **39,238-byte** DOCX with two callers. Median response time was **172.2 ms** and p95 was **240.6 ms**. This measures the stateless audit API with SQLite and no network latency or HTML conversion. At an illustrative compute rate of **$0.10 per busy hour**, attributing a median request’s full duration to compute gives roughly **$0.0000048 per audit**. This is a modeled compute estimate using a measured duration. The actual cost depends on idle capacity, managed database, storage, email, bandwidth and support. At an illustrative $20 monthly fixed hosting cost and 1,000 documents in a month, that fixed cost alone is $0.02 per document. No real invoice or margin is available.

## First ten users

1. Ask one department head to nominate five teachers or TAs who distribute weekly DOCX materials.
2. Ask disability services to help recruit two student readers or accessibility reviewers and host a consented screen-reader session.
3. Invite three more instructors through the first pilot group’s teaching meeting. Give each a sample and one real, permitted document to audit.

## What would count as evidence

Measure documents audited, issues found per document, percentage verified fixed, elapsed time to verified repair, and teachers who return. Collect reader usability observations in facilitated sessions. Published links do not track student opens.

The demo syllabus moved from **2 of 6 to 6 of 6 checks passed**, with **four verified repairs**. That is a synthetic demonstration. Interview five teachers and two students or accessibility staff before asserting demand. Record quotes only with permission and publish findings without student identifiers.

## Limits and roadmap

The checker focuses on six checks in born-digital DOCX. It cannot assess the accuracy of alt text or guarantee legal outcomes. Complex layouts can lose structure during conversion. Manual screen-reader feedback and real user testing remain part of pilot validation.

Prioritize DOCX fixes and real reader testing. Explore PDF and PPTX, additional checks, batch processing, Moodle and Canvas, institutional SAML or OIDC, multilingual readers, offline-first mobile packaging and human reviewer referrals after pilot demand is established.
