# Compass X · Multi-firm walkthrough v2.0 — test report

2026-10-27 · published at https://claude.ai/artifact/9AM1k1mf3fLke3PMbWHvsT · Playwright, headless Chromium

**102/102 checks pass on the final build.**

## What v2.0 adds

| Use case | Journey | Where |
|---|---|---|
| Sign in as a specific steward: group, child firm or standalone | Steward | Firm card in the navigation |
| Child-firm steward limited to their own firm; group-wide people view-only | Steward | Users, request form |
| Delegation ① — the owning firm delegates a slice of its accounts (sub-advisory or referral) | Steward | Relationships → Delegate accounts |
| NBIN checks the agreement and Risk review, then records the delegation | Product Activation | Relationship requests |
| Delegation ② — the receiving firm picks its people, only within what was delegated | Steward | Request form |
| The owner sees who uses its accounts (read-only) | Steward | Users → People from other firms using your accounts |
| The owner confirms the delegation is still valid (attestation of the relationship) | Steward | Relationships |
| Delegation ③ — the owner ends it; access is removed immediately; SZ clean-ups go to the SAA | Steward, or Activation on its behalf | Relationships / Delegations |
| A firm joins or leaves a group, with the effect shown before confirming | Product Activation | Groups |
| Two groups merge (Cumberland into Harbourfront); group-wide profiles flagged for review | Product Activation → Steward | Groups → Users review bar |
| One level only: a parent group cannot sit under another; the reporting grouping can never be used | Product Activation | Groups |

## Defects found by this run and fixed

| # | Defect | Fix |
|---|---|---|
| D1 | Switching steward kept the previous screen (e.g. My requests) instead of landing on that steward's Users | A steward switch always lands on Users; New request has the same id on both screens |
| D2 | Guide steps 7–8 lost their highlight once Fiera's delegation had been ended in the session | Those steps pick any active delegation with users, and fall back to a visible element |
| D3 | The Relationships screen was the only screen without an opening caption | Caption added |
| D4 | Modify subtitle repeated the firm name; lend form had a lowercase sentence start; a child steward's own firm was tagged "Aggregation" | Wording fixed; own firm is tagged "Your firm" |
| D5 (from v1) | Child firm context offered the whole group in the request form | Fixed by signing in as a specific steward |

## Regression (81/81)

| ID | Check | Result |
|---|---|---|
| R01 | Loads without JS errors | Pass |
| R02 | Every firm has at least 4 people of its own | Pass |
| R03 | No duplicate names | Pass |
| R04 | Every steward named in STEWARD_OF exists as a person | Pass |
| R05 | No undefined/NaN on first render | Pass |
| R06 | Three journeys in the top bar | Pass |
| R10 | Harbourfront Group steward sees the whole group (20+ people) | Pass |
| R11 | Group steward caption is tagged Aggregation | Pass |
| R12 | Firm filter shows that firm plus group-wide people who reach it | Pass |
| R13 | Rows stay clickable after search (v1 regression) | Pass |
| R14 | Group steward can manage a child firm person | Pass |
| R20 | Child steward identity shown | Pass |
| R21 | Group-wide holder is listed but view-only for the child steward | Pass |
| R22 | Child steward form offers only their own firm | Pass |
| R23 | Child steward banner explains the limit | Pass |
| R24 | Child steward Modify list excludes group-wide people | Pass |
| R30 | Group steward form offers group + 4 firms | Pass |
| R31 | Submit without a name is blocked | Pass |
| R32 | Duplicate name warning | Pass |
| R33 | Group-wide choice shows the Aggregation banner | Pass |
| R34 | Group-wide choice pre-includes all 4 firms | Pass |
| R35 | Submit without features is blocked | Pass |
| R36 | Create request stored: group-wide, 3 firms, 2 features | Pass |
| R37 | Modify preselects person and firm | Pass |
| R38 | Modify loads current features | Pass |
| R39 | "What this means" explains the move | Pass |
| R40 | Deactivate explains linked IDs and hides choices | Pass |
| R41 | Steward can cancel an open request | Pass |
| R50 | Receiving firm offers a delegated-accounts option | Pass |
| R51 | Delegated choice shows the ①②③ banner with ② as "this request" | Pass |
| R52 | Everything outside the trading bundle is greyed out | Pass |
| R53 | Delegation slices toggle | Pass |
| R54 | Delegated create stored with the 2 chosen slices, trading only | Pass |
| R55 | Owner firm sees the receiving firm’s people option disabled | Pass |
| R56 | Clicking it explains who sets those people up | Pass |
| R57 | Owner sees "People from other firms using your accounts" | Pass |
| R58 | Owner opens a borrower’s person view-only | Pass |
| R59 | Referral owner offers a referral-partner option | Pass |
| R60 | Referral choice keeps only view features | Pass |
| R70 | Relationships shows both how-it-works cards and three sections | Pass |
| R71 | Pending Lakeview request is visible to its steward | Pass |
| R72 | Lend form shows step ① as "this request" | Pass |
| R73 | Lend: receiver required | Pass |
| R74 | Lend: only own accounts (prefix) accepted | Pass |
| R75 | Lend: duplicate of a pending request blocked | Pass |
| R76 | Lend submitted to NBIN as a relationship request | Pass |
| R80 | Activation lands on Relationship requests with 2 open | Pass |
| R81 | Record is disabled until all three checks | Pass |
| R82 | Record enables after the checks | Pass |
| R83 | Approved request becomes an active delegation | Pass |
| R84 | Activation can reject a relationship request | Pass |
| R85 | Delegations screen lists all, with "End on behalf" on active ones | Pass |
| R90 | New delegation appears in the receiving steward’s form | Pass |
| R91 | Modify on an existing delegated profile says the other profile is untouched | Pass |
| R100 | SAA nav: Queue and All users only; no firm menu | Pass |
| R101 | Complete disabled until the checklist is done | Pass |
| R102 | Completing a group-wide Create adds the person | Pass |
| R103 | Completing the Modify promotes Daniel to group-wide at Harbourfront Group | Pass |
| R104 | Completing a delegated Create gives Ivy a trading-only profile on 2 slices | Pass |
| R105 | Nora now holds the Lakeview delegation | Pass |
| R106 | Start moves SUBMITTED to UNDER REVIEW | Pass |
| R107 | Reject closes as REJECTED | Pass |
| R108 | All users lists everyone, with "Managed by" and no actions | Pass |
| R110 | Lakeview now sees Nora using its accounts | Pass |
| R111 | Confirm still valid updates the attestation date | Pass |
| R112 | End preview lists who loses what, and the SZ clean-ups | Pass |
| R113 | Ending removes the slice everywhere | Pass |
| R114 | Theo keeps his home firm only (profile becomes a normal firm profile) | Pass |
| R115 | Clean-up requests created for the Secured Zone IDs | Pass |
| R116 | Ended delegation disappears from the receiving steward’s form | Pass |
| R117 | SAA clean-up removes the Secured Zone ID | Pass |
| R120 | Referral end preview says partners become inactive | Pass |
| R121 | Referral partners become inactive with no profile | Pass |
| R130 | Guide runs 9 steps with a highlight on each | Pass |
| R131 | Finish closes the guide and the drawer | Pass |
| R132 | Guide previews do not change data (Cumberland still a group) | Pass |
| R133 | Help button shows and hides every tip | Pass |
| R134 | No undefined/NaN after all flows | Pass |
| R135 | Dark scheme switches the page background | Pass |
| R136 | Narrow viewport hides the nav, keeps journeys reachable | Pass |
| R137 | No JS errors across the whole run | Pass |

## UAT (21/21)

| ID | Check | Result |
|---|---|---|
| U01 | Aaron: 7/7/7 today → 1 login, 4 SZ IDs; tree reaches all four firms | Pass |
| U02 | Nora: home + delegated profile, ①②③ per delegation, three agreements | Pass |
| U03 | Child-firm steward (Wealth Council) can use a delegation made to its firm | Pass |
| U04 | Claire ends with home + delegated profiles and one login | Pass |
| U05 | Dundee sees Claire using its accounts (and Nora on the older delegation) | Pass |
| U06 | After Dundee ends it, Claire is back to one firm profile; Nora keeps Dundee’s older delegation | Pass |
| U07 | Tricert sets up a referral partner who is visibly a partner, view only | Pass |
| U08 | One level only: Rae & Lipsky Group cannot be added under Guardian | Pass |
| U09 | The reporting grouping can never be added | Pass |
| U10 | Clicking a blocked option explains why and leaves Add disabled | Pass |
| U11 | Remove preview names who loses the firm’s accounts | Pass |
| U12 | Wealth Council is standalone; Aaron loses it; SZ clean-up queued | Pass |
| U13 | Merge preview: 4 firms move, Cumberland dissolves, Joanne flagged | Pass |
| U14 | After merge: Cumberland firms sit under Harbourfront, one level | Pass |
| U15 | Harbourfront steward sees the review banner and Joanne | Pass |
| U16 | Review clears once the Harbourfront steward decides (Joanne now in Cumberland Private Wealth) | Pass |
| U17 | Steward menu: Cumberland gone, its firms under Harbourfront, Wealth Council standalone (alphabetical) | Pass |
| U18 | Every screen in every journey opens with a caption | Pass |
| U19 | Aggregation and delegation are tagged consistently (navy vs amber) | Pass |
| U20 | Drawers share one layout: title, body, footer with Cancel/Close | Pass |
| U21 | No JS errors in the UAT run | Pass |

Not covered (prototype limits): persistence across reloads (refresh resets to seed data), concurrent users, a full accessibility audit.
