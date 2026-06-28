import { cn } from "@/lib/utils";
// FIXME  MC8yOmFIVnBZMlhsdEpUbXRiZm92b2s2Y2tGbGRnPT06ODZjODg2MTk=

function Skeleton({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("animate-pulse rounded-md bg-muted", className)}
      {...props}
    />
  );
}

export { Skeleton };
// NOTE  MS8yOmFIVnBZMlhsdEpUbXRiZm92b2s2Y2tGbGRnPT06ODZjODg2MTk=
