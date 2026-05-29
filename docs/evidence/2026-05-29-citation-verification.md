# Citation verification — 2026-05-29

Primary-source verification of the external citations used in the README,
spec, and ADR canon. Performed during the pre-public portfolio quality gate.

## arXiv:2510.16558 (threat-model source)

- **Fetched**: 2026-05-29 from <https://arxiv.org/abs/2510.16558>.
- **Title (verbatim)**: "A First Look at the Security Issues in the Model
  Context Protocol Ecosystem".
- **Authors (verbatim, in order)**: Xiaofan Li, Xing Gao. **Two authors.**
- **Venue**: accepted to DSN 2026 (per the arXiv submission comments).
- **Scope**: catalogues 67,057 servers across six registries; analyses
  registry/server/host security including server hijacking and invocation
  manipulation.
- **Correction applied**: earlier drafts attributed this paper to
  "Wang et al." This was wrong. All references (README, spec, ADR-002,
  ADR-011, `checks/ATTRIBUTION.md`) were corrected to **"Li and Gao"**
  in commit `78eb84a`.

## earezki (2026-02) — registry source-publication rate

- **Source located**: <https://earezki.com/ai-news/2026-02-21-i-scanned-every-server-in-the-official-mcp-registry-heres-what-i-found/>
  — "41% of Official MCP Servers Lack Authentication: A Security Audit of
  518 AI Agent Tools" (2026-02-21).
- **Verified**: the source is real and is the origin of the "41% lack
  authentication" figure (consistent with the v0.2.0-design threat-surface
  notes). Total surveyed: **518 servers** in the official MCP registry.
- **Resolved by softening**: the exact "84.6% GitHub-hosted source" figure
  previously cited in README Limitations, ADR-002, and the CHANGELOG could
  **not** be byte-verified — the blog returns HTTP 403 to automated fetches,
  the Wayback snapshot was unreachable, and a targeted search did not surface
  the specific percentage. Rather than keep an unverifiable precise number in
  public docs (which would undercut this project's "measure it firsthand"
  stance), the three references were reworded to the qualitative "the majority
  of registry entries", with the firsthand public-source rate deferred to the
  Phase 1.5 Top-50 pilot. The earezki source itself (518 servers, 41% no-auth)
  remains verified and attributed.

## Equixly figures (43% / 22% / 30%)

- **Not cited as fact.** Per README Limitations and the
  `2026-05-29-deep-research-mcp-threat-surface.md` probe, these figures did
  not survive primary-source verification (single blog post, no published
  sample size or methodology). The project explicitly does not cite them.
