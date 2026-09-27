# Phase 25 Stage 6 — Source and gap analysis

## Sources

Pinned OIML sources:

- OIML R 76-1 Edition 2006 (E)
- OIML R 76-2 Edition 2007 (E)

National authority-context sources:

- Legal Metrology (Approval of Models) Rules, 2011
- Legal Metrology (General) Rules, 2011 and applicable amendments
- Government Approved Test Centre rules/context

The national sources are kept separate from OIML technical requirements.

## REG-16

### Equipment / calibration

Source navigation includes R76-1 3.7 test standards and supporting Annex-F
module-report material that records test-equipment/calibration information.

The project currently freezes equipment master identity and, when supplied,
calibration certificate attachment identity, SHA-256 and object version.

This is traceability only. The software does not infer that a certificate is
regulatorily acceptable.

### Environment

R76-1 A.4.1.1 and A.4.1.2 define general-condition/temperature behavior for
tests. Annex B procedures also require environmental conditions to be noted or
recorded where applicable.

The project captures time, temperature, relative humidity, barometric pressure
and phase metadata without inventing test-specific requirements.

### Retest / authoritative selection

The project has immutable retest lineage, explicit selected-run events, stale
result events and review invalidation. Exact regulatory retest triggers and
selection criteria remain dependent on the unverified REG-16 policy.

### Evidence

The project provides hashed/versioned evidence identity, protected links and
approval-snapshot capture. Which evidence items are legally mandatory remains
a regulatory-source question.

## REG-17

OIML R76-2 is a test-report format source, not by itself an authority grant for
national report issue.

The existing reporting stack has safe technical controls for preview,
generation, issue, revision lineage, frozen issuer identity and hashes.

Exact authority conventions for numbering, officer/signature, revision,
publication and record-retention remain separately mapped to Indian Legal
Metrology/GATC sources under REG-17.

## Conclusion

Stage 6 closes the engineering-groundwork gap, not the independent regulatory
verification gap.
