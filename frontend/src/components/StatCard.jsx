export default function StatCard({ label, value, helper, testId }) {
  return (
    <div
      className="interactive-card rounded-lg border border-border bg-card p-5"
      data-testid={`${testId}-card`}
    >
      <p className="text-sm font-medium text-muted-foreground" data-testid={`${testId}-label`}>
        {label}
      </p>
      <p className="mt-3 text-3xl font-bold tracking-tight text-foreground" data-testid={`${testId}-value`}>
        {value}
      </p>
      {helper ? (
        <p className="mt-2 text-xs text-muted-foreground" data-testid={`${testId}-helper`}>
          {helper}
        </p>
      ) : null}
    </div>
  );
}
