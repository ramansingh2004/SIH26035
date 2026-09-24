export function RegulatoryBlocker({ ruleIds = [] }: { ruleIds?: string[] }) {
  return (
    <section
      className="regulatory-blocker"
      aria-label="Regulatory verification required"
    >
      <div className="regulatory-blocker-mark" aria-hidden="true">
        !
      </div>
      <div>
        <h3>Regulatory verification required</h3>
        <p>
          This evaluation cannot proceed to an authoritative compliance result
          until the required regulatory rule evidence has been verified.
        </p>
        {ruleIds.length > 0 ? (
          <p className="regulatory-rule-list">
            Unresolved rules: {ruleIds.join(", ")}
          </p>
        ) : null}
        <span className="status-chip status-warning">
          TODO_REGULATORY_VALIDATION
        </span>
      </div>
    </section>
  );
}
