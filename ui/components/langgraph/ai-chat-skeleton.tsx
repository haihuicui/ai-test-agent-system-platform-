import { Skeleton } from "@/components/ui/skeleton";

export function AIChatSkeleton() {
  return (
    <div className="flex h-full flex-col gap-4 p-4">
      <Skeleton className="h-8 w-48" />
      <div className="flex-1 space-y-3">
        <Skeleton className="h-12 w-3/4" />
        <Skeleton className="h-12 w-1/2" />
        <Skeleton className="h-12 w-2/3" />
      </div>
      <Skeleton className="h-16 w-full" />
    </div>
  );
}
