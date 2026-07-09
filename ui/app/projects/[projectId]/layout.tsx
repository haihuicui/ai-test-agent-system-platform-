import * as React from "react";
import { ProjectEnvironmentProvider } from "@/providers/ProjectEnvironmentProvider";

export default function ProjectLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: { projectId: string };
}) {
  return (
    <ProjectEnvironmentProvider projectId={params.projectId}>
      {children}
    </ProjectEnvironmentProvider>
  );
}
