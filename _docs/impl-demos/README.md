# Implementation demos

This directory holds small, self-contained demonstration assets that documentation elsewhere in
the repository refers to. They are examples, not product code: nothing under `backend/` or
`frontend/` imports them, and no test collects them.

## Vendor files

`d3.min.js` is a vendored copy of the d3 visualisation library.

- Project: <https://d3js.org>
- Version delivered: 8
- License: ISC (Copyright Node.js Foundation and contributors)
- License text: <https://raw.githubusercontent.com/d3/d3/main/LICENSE>

Redistribution under the ISC terms is permitted, and the full license text is shipped next to the
file as `d3.LICENSE`.

## Rules for this directory

1. Every file here must be something the documentation actually links to. If the link is removed,
   delete the asset in the same change.
2. Never place a generated, machine-specific or secret-bearing file here.
   Anything generated belongs in a path the repository ignores.
3. Any third-party asset must ship its license text in this directory, and this README must name
   the project, the version and the license.
4. Vendor assets are pinned by content, not by a moving tag. Record the version in this README when
   a file is added or replaced, so a later reader can tell whether the copy is stale.
