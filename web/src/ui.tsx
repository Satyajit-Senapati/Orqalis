export const label = (value: string) => value.replaceAll("_", " ").toLowerCase();
export const count = (value: number | null | undefined) => value == null ? "Not reported" : value.toLocaleString();
export function Badge({ status }: { status: string }) {
  return <span className={`badge status-${status.toLowerCase()}`}><i />{label(status)}</span>;
}
export function Empty({ children }: { children: React.ReactNode }) {
  return <div className="empty small-empty"><p>{children}</p></div>;
}
