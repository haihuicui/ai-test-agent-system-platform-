"use client";
// eslint-disable  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2TWtsclNRPT06NjYyNWI3YTE=

import * as React from "react";
import { useRouter } from "next/navigation";
import {
  Plus,
  Search,
  Star,
  StarOff,
  MoreHorizontal,
  Pencil,
  Trash2,
  FolderKanban,
  FileText,
  Bot,
} from "lucide-react";
import { toast } from "sonner";
import { MainLayout } from "@/components/layout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Badge } from "@/components/ui/badge";
import {
  getProjects,
  createProject,
  updateProject,
  deleteProject,
} from "@/lib/api/projects";
import type { ProjectInfo, ProjectCreate } from "@/lib/api/types";
import { useLanguage } from "@/providers/LanguageProvider";
// WATERMARK  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2TWtsclNRPT06NjYyNWI3YTE=

export default function ProjectsPage() {
  const router = useRouter();
  const { t } = useLanguage();
  const [projects, setProjects] = React.useState<ProjectInfo[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [searchQuery, setSearchQuery] = React.useState("");
  const [starredProjects, setStarredProjects] = React.useState<Set<string>>(
    new Set()
  );

  // AI 代理展示数据
  const aiAgents = [
    {
      id: 1,
      name: t("ai.testCaseGenerator"),
      description: t("ai.testCaseGeneratorDesc"),
      icon: "🤖",
      status: "active",
    },
    {
      id: 2,
      name: t("ai.defectAnalyzer"),
      description: t("ai.defectAnalyzerDesc"),
      icon: "🔍",
      status: "active",
    },
    {
      id: 3,
      name: t("ai.regressionOptimizer"),
      description: t("ai.regressionOptimizerDesc"),
      icon: "⚡",
      status: "coming",
    },
  ];

  // 对话框状态
  const [createDialogOpen, setCreateDialogOpen] = React.useState(false);
  const [editDialogOpen, setEditDialogOpen] = React.useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = React.useState(false);
  const [selectedProject, setSelectedProject] =
    React.useState<ProjectInfo | null>(null);

  // 表单状态
  const [formData, setFormData] = React.useState<ProjectCreate>({
    name: "",
    description: "",
  });
  const [submitting, setSubmitting] = React.useState(false);

  // 加载项目列表
  const loadProjects = React.useCallback(async () => {
    try {
      setLoading(true);
      const response = await getProjects({ page_size: 100 });
      if (response.success && response.data) {
        setProjects(response.data);
      }
    } catch (error) {
      console.error("Failed to load projects:", error);
      toast.error(t("projects.loadFailed"));
    } finally {
      setLoading(false);
    }
  }, [t]);

  React.useEffect(() => {
    loadProjects();
    // 从 localStorage 加载收藏状态
    const saved = localStorage.getItem("starredProjects");
    if (saved) {
      setStarredProjects(new Set(JSON.parse(saved)));
    }
  }, [loadProjects]);

  // 过滤项目
  const filteredProjects = React.useMemo(() => {
    if (!searchQuery) return projects;
    const query = searchQuery.toLowerCase();
    return projects.filter(
      (p) =>
        p.name.toLowerCase().includes(query) ||
        p.description?.toLowerCase().includes(query)
    );
  }, [projects, searchQuery]);

  // 收藏/取消收藏
  const toggleStar = (projectId: string) => {
    const newStarred = new Set(starredProjects);
    if (newStarred.has(projectId)) {
      newStarred.delete(projectId);
    } else {
      newStarred.add(projectId);
    }
    setStarredProjects(newStarred);
    localStorage.setItem("starredProjects", JSON.stringify(Array.from(newStarred)));
  };

  // 创建项目
  const handleCreate = async () => {
    if (!formData.name.trim()) {
      toast.error(t("projects.enterProjectName"));
      return;
    }
    try {
      setSubmitting(true);
      const response = await createProject(formData);
      if (response.success) {
        toast.success(t("projects.projectCreated"));
        setCreateDialogOpen(false);
        setFormData({ name: "", description: "" });
        loadProjects();
      }
    } catch (error) {
      console.error("Failed to create project:", error);
      toast.error(t("projects.createFailed"));
    } finally {
      setSubmitting(false);
    }
  };

  // 更新项目
  const handleUpdate = async () => {
    if (!selectedProject || !formData.name.trim()) {
      toast.error(t("projects.enterProjectName"));
      return;
    }
    try {
      setSubmitting(true);
      const response = await updateProject(selectedProject.identifier, formData);
      if (response.success) {
        toast.success(t("projects.projectUpdated"));
        setEditDialogOpen(false);
        setSelectedProject(null);
        setFormData({ name: "", description: "" });
        loadProjects();
      }
    } catch (error) {
      console.error("Failed to update project:", error);
      toast.error(t("projects.updateFailed"));
    } finally {
      setSubmitting(false);
    }
  };

  // 删除项目
  const handleDelete = async () => {
    if (!selectedProject) return;
    try {
      setSubmitting(true);
      const response = await deleteProject(selectedProject.identifier);
      if (response.success) {
        toast.success(t("projects.projectDeleted"));
        setDeleteDialogOpen(false);
        setSelectedProject(null);
        loadProjects();
      }
    } catch (error) {
      console.error("Failed to delete project:", error);
      toast.error(t("projects.deleteFailed"));
    } finally {
      setSubmitting(false);
    }
  };

  // 打开编辑对话框
  const openEditDialog = (project: ProjectInfo) => {
    setSelectedProject(project);
    setFormData({
      name: project.name,
      description: project.description || "",
    });
    setEditDialogOpen(true);
  };

  // 打开删除对话框
  const openDeleteDialog = (project: ProjectInfo) => {
    setSelectedProject(project);
    setDeleteDialogOpen(true);
  };

  // 进入项目
  const enterProject = (project: ProjectInfo) => {
    router.push(`/projects/${project.identifier}/test-cases`);
  };

  return (
    <MainLayout title={t("projects.title")}>
      <div className="space-y-6">
        {/* AI 代理展示区 */}
        <div className="rounded-lg border bg-gradient-to-r from-primary/5 to-primary/10 p-6">
          <div className="mb-4 flex items-center gap-2">
            <Bot className="h-5 w-5 text-primary" />
            <h2 className="text-lg font-semibold">{t("ai.title")}</h2>
          </div>
          <div className="grid gap-4 md:grid-cols-3">
            {aiAgents.map((agent) => (
              <div
                key={agent.id}
                className="rounded-lg border bg-card p-4 transition-shadow hover:shadow-md"
              >
                <div className="mb-2 flex items-center justify-between">
                  <span className="text-2xl">{agent.icon}</span>
                  <Badge
                    variant={agent.status === "active" ? "default" : "secondary"}
                  >
                    {agent.status === "active" ? t("ai.available") : t("ai.comingSoon")}
                  </Badge>
                </div>
                <h3 className="font-medium">{agent.name}</h3>
                <p className="mt-1 text-sm text-muted-foreground">
                  {agent.description}
                </p>
              </div>
            ))}
          </div>
        </div>

        {/* 项目列表区 */}
        <div className="rounded-lg border bg-card">
          <div className="flex items-center justify-between border-b p-4">
            <h2 className="text-lg font-semibold">{t("projects.myProjects")}</h2>
            <div className="flex items-center gap-3">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  placeholder={t("projects.searchProjects")}
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-64 pl-9"
                />
              </div>
              <Button onClick={() => setCreateDialogOpen(true)}>
                <Plus className="mr-2 h-4 w-4" />
                {t("projects.newProject")}
              </Button>
            </div>
          </div>

          {loading ? (
            <div className="flex h-64 items-center justify-center">
              <div className="text-muted-foreground">{t("common.loading")}</div>
            </div>
          ) : filteredProjects.length === 0 ? (
            <div className="flex h-64 flex-col items-center justify-center gap-2">
              <FolderKanban className="h-12 w-12 text-muted-foreground/50" />
              <p className="text-muted-foreground">
                {searchQuery ? t("projects.noMatchingProjects") : t("projects.noProjects")}
              </p>
            </div>
          ) : (
            <div className="grid gap-4 p-4 md:grid-cols-2 lg:grid-cols-3">
              {filteredProjects.map((project) => (
                <div
                  key={project.identifier}
                  className="group cursor-pointer rounded-lg border p-4 transition-all hover:border-primary hover:shadow-md"
                  onClick={() => enterProject(project)}
                >
                  <div className="mb-3 flex items-start justify-between">
                    <div className="flex items-center gap-2">
                      <FolderKanban className="h-5 w-5 text-primary" />
                      <h3 className="font-medium">{project.name}</h3>
                    </div>
                    <div className="flex items-center gap-1">
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8"
                        onClick={(e) => {
                          e.stopPropagation();
                          toggleStar(project.identifier);
                        }}
                      >
                        {starredProjects.has(project.identifier) ? (
                          <Star className="h-4 w-4 fill-yellow-400 text-yellow-400" />
                        ) : (
                          <StarOff className="h-4 w-4" />
                        )}
                      </Button>
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-8 w-8"
                            onClick={(e) => e.stopPropagation()}
                          >
                            <MoreHorizontal className="h-4 w-4" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem
                            onClick={(e) => {
                              e.stopPropagation();
                              openEditDialog(project);
                            }}
                          >
                            <Pencil className="mr-2 h-4 w-4" />
                            {t("common.edit")}
                          </DropdownMenuItem>
                          <DropdownMenuItem
                            className="text-destructive"
                            onClick={(e) => {
                              e.stopPropagation();
                              openDeleteDialog(project);
                            }}
                          >
                            <Trash2 className="mr-2 h-4 w-4" />
                            {t("common.delete")}
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </div>
                  </div>
                  <p className="mb-3 line-clamp-2 text-sm text-muted-foreground">
                    {project.description || t("common.noDescription")}
                  </p>
                  <div className="flex items-center gap-4 text-sm text-muted-foreground">
                    <div className="flex items-center gap-1">
                      <FileText className="h-4 w-4" />
                      <span>{project.test_cases_count} {t("projects.testCasesCount")}</span>
                    </div>
                    <div className="flex items-center gap-1">
                      <FolderKanban className="h-4 w-4" />
                      <span>{project.folders_count} {t("projects.foldersCount")}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* 创建项目对话框 */}
      <Dialog open={createDialogOpen} onOpenChange={setCreateDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("projects.newProject")}</DialogTitle>
            <DialogDescription>{t("projects.createNewProject")}</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="name">{t("projects.projectName")}</Label>
              <Input
                id="name"
                value={formData.name}
                onChange={(e) =>
                  setFormData({ ...formData, name: e.target.value })
                }
                placeholder={t("projects.enterProjectName")}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="description">{t("projects.projectDescription")}</Label>
              <Textarea
                id="description"
                value={formData.description}
                onChange={(e) =>
                  setFormData({ ...formData, description: e.target.value })
                }
                placeholder={t("projects.enterProjectDescription")}
                rows={3}
              />
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setCreateDialogOpen(false)}
            >
              {t("common.cancel")}
            </Button>
            <Button onClick={handleCreate} disabled={submitting}>
              {submitting ? t("common.creating") : t("common.create")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* 编辑项目对话框 */}
      <Dialog open={editDialogOpen} onOpenChange={setEditDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("projects.editProject")}</DialogTitle>
            <DialogDescription>{t("projects.editProjectInfo")}</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="edit-name">{t("projects.projectName")}</Label>
              <Input
                id="edit-name"
                value={formData.name}
                onChange={(e) =>
                  setFormData({ ...formData, name: e.target.value })
                }
                placeholder={t("projects.enterProjectName")}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="edit-description">{t("projects.projectDescription")}</Label>
              <Textarea
                id="edit-description"
                value={formData.description}
                onChange={(e) =>
                  setFormData({ ...formData, description: e.target.value })
                }
                placeholder={t("projects.enterProjectDescription")}
                rows={3}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditDialogOpen(false)}>
              {t("common.cancel")}
            </Button>
            <Button onClick={handleUpdate} disabled={submitting}>
              {submitting ? t("common.saving") : t("common.save")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* 删除确认对话框 */}
      <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("projects.deleteProject")}</DialogTitle>
            <DialogDescription>
              {t("projects.deleteConfirm", { name: selectedProject?.name || "" })}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setDeleteDialogOpen(false)}
            >
              {t("common.cancel")}
            </Button>
            <Button
              variant="destructive"
              onClick={handleDelete}
              disabled={submitting}
            >
              {submitting ? t("common.deleting") : t("common.delete")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </MainLayout>
  );
}
// WATERMARK  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2TWtsclNRPT06NjYyNWI3YTE=

// WATERMARK  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2TWtsclNRPT06NjYyNWI3YTE=
