"""
Provenance labels separating measured facts from our own estimates.

Why this module exists:

The CPI figures in this app are **ingested** — read directly off MOSPI's
press-release PDFs. They match the official print exactly, by construction,
because they ARE the official print. They are not forecasts and carry no
error.

The basket index is the opposite: an **independent estimate** built from
retail grocery prices, whose distance from the official print is a real,
measurable quantity — and currently an unmeasured one.

Conflating the two is the most damaging thing this product can do to its own
credibility. A reader who mistakes the ingested CPI for our estimate
concludes the system forecasts inflation exactly, which is not a claim anyone
can honestly make and which collapses the moment someone asks how. These
labels exist so a viewer can never draw that conclusion from the screen.

Keep both strings blunt. Hedged wording is what creates the ambiguity.
"""

OFFICIAL_INGESTED = (
    "**Official MOSPI figure — ingested, not estimated.** Read directly from the "
    "press-release PDF, so it matches the published print exactly by construction. "
    "The decomposition and commentary below are ours; the headline is not a forecast."
)

INDEPENDENT_ESTIMATE = (
    "**Independent estimate — not an official figure, and not yet validated.** Built "
    "from retail grocery prices separately from MOSPI. Its tracking error against the "
    "official CPI print has not been measured, so no accuracy claim is made here."
)
