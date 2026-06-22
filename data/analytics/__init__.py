"""Shared analytics layer for the STATpy dashboards.

Contains the PD performance calculation engine (:mod:`calculations`), the
MEV range helpers (:mod:`mev_range`), the scenario rank-ordering helpers
(:mod:`rank_ordering`) and the data-domain constants (:mod:`constants`).

These modules are imported by the shared ``components/`` layer *and* by more
than one dashboard, so by the "rule of two" they live in a shared location
rather than inside a single dashboard package.
"""
