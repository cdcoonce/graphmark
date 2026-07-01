---
date: 2026-07-01
description: "OUT-of-scope note under misc/. Must not be scanned; its link to one must not create a back-edge."
tags: [fixture]
---

# Excluded

I live under misc/, which is NOT in scoped_folders, so I should be absent from the graph. I even
link to [[one]] — and that link must NOT appear as a back-link on one, proving links originating in
out-of-scope folders are ignored, not merely that out-of-scope nodes are hidden.
