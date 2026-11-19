# canonicalization — format translation layer between agent output and compiler input.
#
# Invariants (enforced throughout this package):
#   I1 — Translation, not creation: if information is absent from the input, the
#        canonicalizer writes null/[] — it never invents values.
#   I2 — Optional enrichment: architecture_map.json improves quality but is never
#        required to produce valid compiler output.
#   I3 — Report, don't judge: --validate reports coverage metrics; it only fails
#        on structural contract violations, not on agent quality signals.
