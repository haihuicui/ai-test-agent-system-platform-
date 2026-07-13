import { Skeleton } from "@/components/ui/skeleton";

export function ProjectPageSkeleton() {
  return (
    <div className="flex h-[calc(100vh-8rem)] rounded-lg border bg-card overflow-hidden">
      <div className="w-80 shrink-0 border-r bg-card p-3 space-y-3">
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-8 w-full" />
        <Skeleton className="h-8 w-full" />
        <Skeleton className="h-8 w-full" />
      </div>
      <div className="flex-1 p-6 space-y-4">
        <div className="flex items-center justify-between">
          <Skeleton className="h-8 w-48" />
          <Skeleton className="h-8 w-32" />
        </div>
        <Skeleton className="h-[calc(100%-4rem)] w-full" />
      </div>
    </div>
  );
}

export function ListPageSkeleton() {
  return (
    <div className="space-y-6">
      <Skeleton className="h-10 w-64" />
      <div className="flex items-center justify-between">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-8 w-32" />
      </div>
      <Skeleton className="h-32 w-full" />
      <Skeleton className="h-64 w-full" />
    </div>
  );
}
