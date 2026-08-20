# Vowelchemy for Undergraduate Researchers — Improvement Plan

*Audience for this plan: an undergraduate who has taken (or is taking) an intro
linguistics/phonetics course and wants to get their feet wet with **real
research** — a course paper, a poster, an honors thesis, or an RA-ship in the
lab. They are not yet fluent in statistics, scripting, or the sociophonetics
literature. Vowelchemy already lowers the* mechanical *barrier (align → extract
→ normalize → plot → measure). This plan is about lowering the* scientific
*barrier: helping a student go from "I can make a violin plot" to "I asked a
question, analyzed data defensibly, and wrote it up."*

Priority: **P0** (do first — highest leverage) · **P1** · **P2**.
Effort: **S** ≈ hours · **M** ≈ a day · **L** ≈ multi-day.

---

## Where a new researcher gets stuck today

Walking the current app as a student with a research idea ("are LOT and
THOUGHT merged for people my age?"):

1. **They can produce output, but don't know what to *ask*.** The tool starts
   from data, not from a research question. Nothing helps them turn curiosity
   into an operationalized question (which vowels, which groups, which
   measure, what would count as evidence).
2. **They can compute JSD/Pillai, but don't know what to *report*.** The
   verdict line helps interpretation, but there's no guidance on what belongs
   in a results paragraph (Ns, CIs, the normalization used, exclusions).
3. **Writing the Methods section is a bigger blocker than running the
   analysis.** Every choice the tool made for them (Lobanov, midpoint
   measurement, outlier SD, MFA model) needs prose and citations they don't
   know how to produce.
4. **One demo phenomenon.** The synthetic corpus shows one merger. A student
   can't practice on a *second* problem to test whether they've learned the
   workflow or just memorized the demo.
5. **No trail of what they did.** When a supervisor asks "what exactly did you
   run?", the recipe JSON answers it — but students don't know that's the
   answer, and it isn't human-readable.
6. **Statistical guardrails are silent.** Nothing warns them that 7 tokens in
   a cell is too few, that unbalanced groups distort pooled comparisons, or
   that running 20 pairwise tests inflates false positives.

---

## The plan

### Phase 1 — "From question to defensible answer" (P0)

**1.1 Research-question wizard (P0 · M).**
A new entry point (or Stage-4 panel): pick a question template —
*"Are ⟨A⟩ and ⟨B⟩ merged for ⟨group⟩?"*, *"Does ⟨vowel⟩'s ⟨F1/F2⟩ differ by
⟨factor⟩?"*, *"Is ⟨vowel⟩ changing in apparent time?"* — and the app
pre-configures the right vowel selection, grouping, plot type, and metric,
with one paragraph explaining *why* those are the right instruments for that
question. Templates are data: easy for a lab to add their own.

**1.2 Methods-paragraph generator (P0 · M).**
A "📄 Methods text" button that renders the current recipe as citable prose:

> *Vowel tokens (N = 3,986 after excluding 514 outliers > 2.5 SD from
> speaker×vowel means) were force-aligned with the Montreal Forced Aligner
> (McAuliffe et al., 2017) and formants measured with new-fave (Fruehwald,
> 2024). Formants were normalized using Lobanov's (1971) z-score method.
> Category separation was quantified with Jensen–Shannon Divergence (Lin,
> 1991) with 200-sample bootstrap CIs…*

Copy button + BibTeX for the cited works (references now ship with the repo —
see `docs/REFERENCES.md`). This single feature converts tool output into the
start of a paper.

**1.3 "What to report" checklist under Separation (P0 · S).**
A collapsible panel: report the metric *and* its CI, both Ns, the
normalization, the space (F1×F2 vs F1-only), and the exclusion rule; never
report a merger claim from a point estimate alone. Each line links to the
glossary.

**1.4 Statistical guardrails (P0 · S–M).**
Inline warnings, not blockers: cells with n < 20 tokens flagged in the
separation table; unbalanced group sizes noted; a multiple-comparisons note
when > 3 pairs are computed at once (with a Holm-corrected p option on the
Pillai permutation test).

### Phase 2 — "Practice makes a researcher" (P0/P1)

**2.1 A second and third demo corpus (P0 · M).**
Synthetic corpora with different, classic phenomena so students can practice
transfer, not recall: (a) **PIN~PEN merger** conditioned on a regional
"Dialect" column (pre-nasal /ɪ/~/ɛ/), (b) **/u/-fronting** in apparent time
(a *shift*, not a merger — teaches that JSD alone isn't the question),
(c) a **null corpus** where nothing is going on — arguably the most important
one, because recognizing "no effect" is a research skill.

**2.2 Guided replication tutorial (P0 · M).**
`docs/TUTORIAL.md` + an in-app "Tutorial" link: a 45-minute, screenshot-free
walkthrough that replicates the demo merger end-to-end — question →
hypothesis → analysis → interpretation → limitations — with "check yourself"
answers (expected JSD per age group ±0.05). Ends by pointing at demo corpus
(b) as an unguided exercise.

**2.3 Mystery-corpus mode (P1 · S).**
`vowelchemy demo --mystery N` writes one of the synthetic corpora with the
phenomenon *unlabeled* (and slight parameter jitter); an answer key goes to a
separate file. Instructors can hand a class the corpus and keep the key.

### Phase 3 — "Show your work" (P1)

**3.1 Human-readable lab notebook (P1 · M).**
An append-only, per-project log of analysis actions ("loaded 4,500 tokens",
"switched to Labov ANAE (G=6.896874)", "computed AA~AO by Age Group: JSD
0.10 [0.06, 0.15]") viewable in the sidebar and exportable as markdown — the
appendix a supervisor actually wants, generated for free.

**3.2 Poster/paper export bundle (P1 · M).**
One click on a finished analysis: a zip with every current figure as SVG +
PNG, the stats table as CSV, the methods paragraph (1.2), the notebook
(3.1), the recipe JSON, and `references.bib`. "Everything you need to leave
the tool and start writing."

**3.3 Share-a-project file (P1 · S).**
Projects already persist server-side; add export/import of a project as a
single `.vowelchemy.zip` so a student can email their exact analysis to a
supervisor who opens it in their own instance.

### Phase 4 — "Join the research community" (P2)

**4.1 Annotated reading list in the glossary (P2 · S).**
Each glossary entry gains a "read more" line pointing at the canonical paper
(now in `docs/REFERENCES.md`) with one sentence on why it matters — e.g.
Lobanov (1971) for why we normalize; Nycz & Hall-Lew (2013) for how mergers
are measured in practice.

**4.2 Ethics & data-handling primer (P2 · S).**
`docs/WORKING_WITH_SPEECH_DATA.md`: consent and IRB basics, why speech is
identifying data, anonymization of speaker codes, and why the folder-browser
confinement exists. Required reading before a student touches lab recordings.

**4.3 Student CONTRIBUTING.md (P2 · S).**
"Getting your feet wet with research" includes research *software*: a
contributor guide with three genuinely small, well-scoped first issues (add a
vowel-label map for another dialect/language; add a question template; add a
glossary entry with its reference), and the dev-loop commands.

**4.4 Classroom mode (P2 · L).**
Multi-user niceties for lab teaching: named per-student sessions, a
read-only "instructor view" of a student's project, and an instructor-set
default recipe. (Requires real auth — deliberately last.)

---

## Sequencing & rationale

| Order | Items | Why first |
|---|---|---|
| 1 | 1.2 Methods generator, 1.3 report checklist, 1.4 guardrails | Converts existing output into *research* output; small code, huge credibility win |
| 2 | 2.1 extra demo corpora, 2.2 tutorial | Practice + transfer; unblocks self-teaching without a supervisor present |
| 3 | 1.1 question wizard | Bigger UI lift; lands best once corpora/tutorial exist to exercise it |
| 4 | 3.1–3.3 notebook, export bundle, share file | Supervisor-facing workflow; builds on recipe/projects already shipped |
| 5 | Phase 4 | Community & classroom; valuable but not blocking anyone's first study |

**Explicit non-goals for this audience:** mixed-effects modeling UI (send
students to R at that point — the CSV export is the bridge), real-time audio
recording, and non-vowel segments. The tool should stay a sharp on-ramp, not
become a statistics package.

---

## Success criteria

A sophomore with one phonetics course, given only the README and tutorial,
can — in one sitting, with no help — (1) load a mystery corpus, (2) identify
which vowel pair shows a change and in which group, (3) produce a figure +
metric + CI supporting it, and (4) export a methods paragraph and reference
list that their instructor would accept in a draft. Every phase-1/2 item
serves that test directly.
