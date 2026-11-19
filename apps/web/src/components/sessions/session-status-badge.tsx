import { Badge } from "@/components/ui/badge";
import { statusVariant } from "@/lib/session-format";

export function SessionStatusBadge({ status }: { status: string }) {
  return (
    <Badge variant={statusVariant(status)} className="capitalize">
      {status}
    </Badge>
  );
}
