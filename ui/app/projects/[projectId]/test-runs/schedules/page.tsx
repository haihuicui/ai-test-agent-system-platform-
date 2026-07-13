import { redirect } from "next/navigation";

export default function SchedulesPage({
  params,
}: {
  params: { projectId: string };
}) {
  redirect(`/projects/${params.projectId}/test-runs?tab=scheduled`);
}
