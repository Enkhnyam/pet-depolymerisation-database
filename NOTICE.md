# What is in this repository, and what is not

## The code

MIT, in `LICENSE`. That covers everything in this repository, because everything in this
repository is ours.

## The papers

Not here. The corpus behind the published database is 1,027 articles, and most of them reached us
under institutional text-and-data-mining entitlements with Elsevier, Wiley and Springer. Those
entitlements permit reading and mining; they do not permit redistribution. The remainder are open
access, from Europe PMC and Unpaywall.

No article text, converted or original, is published here. An earlier version of this repository
tracked `artifacts/backup/`, which carried the converted full text of the 24 benchmark papers —
only 7 of which carry a licence that would have allowed it. That folder has been removed from the
working tree and from the history, and `.gitignore` now excludes all of `artifacts/`.

`licenses.json` is the allowlist that governs redistribution of paper-derived text elsewhere in
the project: the seven papers with an author-licensed open-access copy, which `core/deposit.py`
uses to decide what a deposit bundle may include. `cli/deposit.py` writes the attribution file
that CC BY and CC BY-NC-SA both require.

A caveat worth stating plainly: for five of those seven the open licence attaches to a
*submitted-version* deposit in an institutional repository, not to the publisher's typeset
article. Redistributing the text is within those terms; redistributing the publisher's PDF would
not be, and is not done anywhere in this project.

## The released dataset

It is in `data/`, and it is extracted values — numbers and names read out of papers — together with the
identifiers of the text chunks each value came from and the judge's short critique of it. Facts
are not copyrightable, and no article text travels with them: recovering the passage behind an
identifier requires your own access to the paper.

It is released under CC BY 4.0. That licence covers the extracted data, not the articles it was
read from, which remain under their publishers' terms.

## Model output

Run bundles under `artifacts/` hold what the models returned — records and verdicts, not paper
text. They are excluded from this repository for size rather than for licensing.
