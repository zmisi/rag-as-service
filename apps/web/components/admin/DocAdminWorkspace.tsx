"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { AddFilesModal, type AddFilesPayload } from "@/components/admin/AddFilesModal";
import { AddMemberModal, type AddMemberValues } from "@/components/admin/AddMemberModal";
import { CreateKnowledgeBaseModal } from "@/components/admin/CreateKnowledgeBaseModal";
import { DocEditor } from "@/components/admin/DocEditor";
import { DocSidebar } from "@/components/admin/DocSidebar";
import { FolderBrowser } from "@/components/admin/FolderBrowser";
import { ReviewTaskDetail } from "@/components/admin/ReviewTaskDetail";
import type { ReviewDecisionValues } from "@/components/admin/ReviewDecisionModal";
import {
  getAuthMe,
  createDocument,
  createTenantMember,
  createFolder,
  deleteFolder,
  getDocument,
  getIngestStatus,
  listTenantMembers,
  listDocuments,
  listFolderLayer,
  listFolderReviewers,
  listReviewTasks,
  listFolderTree,
  moveDocumentToFolder,
  moveFolder,
  newDocumentVersion,
  completeDocumentReview,
  publishDocument,
  renameFolder,
  saveDocument,
  submitForReview,
  uploadDocumentFile,
  deleteDocument,
  downloadDocument,
  type FolderLayer,
  type FolderNode,
  type FolderVisibility,
  type ReviewerOption,
  type ReviewTask,
  type TenantMember,
} from "@/lib/api";
import type { DocDetail, DocSummary, IngestJobStatus } from "@/lib/documents";
import { fileTypeRejectMessage, isAllowedFile, MAX_FILE_BYTES } from "@/lib/documents";

function pickTargetFolder(
  tree: FolderNode[],
  excludeId?: string | null,
  promptLabel = "移动到哪个文件夹？",
): string | null | undefined {
  const options = tree.filter((f) => f.folder_id !== excludeId);
  const lines = [
    promptLabel,
    "",
    "0 = 根目录（主页）",
    ...options.map((f, i) => `${i + 1} = ${f.name}`),
    "",
    "输入序号后确认；取消则放弃。",
  ];
  const raw = window.prompt(lines.join("\n"), "0");
  if (raw == null) return undefined;
  const idx = Number.parseInt(raw.trim(), 10);
  if (!Number.isFinite(idx) || idx < 0 || idx > options.length) {
    window.alert("无效序号");
    return undefined;
  }
  if (idx === 0) return null;
  return options[idx - 1]?.folder_id ?? null;
}

export function DocAdminWorkspace() {
  const [documents, setDocuments] = useState<DocSummary[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<DocDetail | null>(null);
  const [title, setTitle] = useState("");
  const [tag, setTag] = useState("");
  const [search, setSearch] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [warning, setWarning] = useState<string | null>(null);
  const [validationErrors, setValidationErrors] = useState<string[]>([]);
  const [ingestJob, setIngestJob] = useState<IngestJobStatus | null>(null);
  const [tree, setTree] = useState<FolderNode[]>([]);
  const [layer, setLayer] = useState<FolderLayer | null>(null);
  const [currentFolderId, setCurrentFolderId] = useState<string | null>(null);
  const [selectedNav, setSelectedNav] = useState<"home" | "knowledge" | "reviewTasks" | "permissions">("home");
  const [selectedPermissionSection, setSelectedPermissionSection] = useState<"members">("members");
  const [createKbOpen, setCreateKbOpen] = useState(false);
  const [addFilesOpen, setAddFilesOpen] = useState(false);
  const [addMemberOpen, setAddMemberOpen] = useState(false);
  const [reviewers, setReviewers] = useState<ReviewerOption[]>([]);
  const [reviewTasks, setReviewTasks] = useState<ReviewTask[]>([]);
  const [members, setMembers] = useState<TenantMember[]>([]);
  const [createdMemberPassword, setCreatedMemberPassword] = useState<string | null>(null);
  const [viewerRole, setViewerRole] = useState<"owner" | "admin" | "member" | null>(null);

  const viewingDoc = Boolean(selectedId) && selectedNav === "knowledge";
  const viewingReviewDoc = Boolean(selectedId) && selectedNav === "reviewTasks";
  const canManageMembers = viewerRole === "owner" || viewerRole === "admin";
  const canReviewTasks = canManageMembers;
  const activeReviewTask = useMemo(
    () => reviewTasks.find((item) => item.doc_id === selectedId) ?? null,
    [reviewTasks, selectedId],
  );

  const breadcrumb = useMemo(() => layer?.breadcrumb ?? [], [layer]);
  const knowledgeBases = useMemo(
    () => tree.filter((f) => f.parent_id == null),
    [tree],
  );

  const refreshAll = useCallback(async (folderId: string | null) => {
    const [items, treeItems, layerData] = await Promise.all([
      listDocuments(),
      listFolderTree(),
      listFolderLayer(folderId),
    ]);
    setDocuments(items);
    setTree(treeItems);
    setLayer(layerData);
    return { items, treeItems, layerData };
  }, []);

  const loadDetail = useCallback(async (id: string, opts?: { preserveForm?: boolean }) => {
    const doc = await getDocument(id);
    setDetail(doc);
    if (!opts?.preserveForm) {
      setTitle(doc.title);
      setTag(doc.tag);
    }
    setValidationErrors([]);
    if (doc.status === "published") {
      const job = await getIngestStatus(id);
      setIngestJob(job);
    } else {
      setIngestJob(null);
    }
  }, []);

  useEffect(() => {
    void refreshAll(null).catch((e) =>
      setError(e instanceof Error ? e.message : "加载失败"),
    );
  }, [refreshAll]);

  useEffect(() => {
    void listFolderReviewers()
      .then(setReviewers)
      .catch(() => setReviewers([]));
  }, []);

  useEffect(() => {
    if (!canReviewTasks) {
      setReviewTasks([]);
      return;
    }
    if (selectedNav !== "reviewTasks") {
      return;
    }
    void listReviewTasks()
      .then(setReviewTasks)
      .catch(() => setReviewTasks([]));
  }, [canReviewTasks, selectedNav]);

  useEffect(() => {
    void getAuthMe()
      .then((me) => setViewerRole(me.role ?? null))
      .catch(() => setViewerRole(null));
  }, []);

  useEffect(() => {
    if (!canManageMembers) {
      setMembers([]);
      return;
    }
    void listTenantMembers()
      .then(setMembers)
      .catch(() => setMembers([]));
  }, [canManageMembers]);

  useEffect(() => {
    if (!selectedId) {
      setDetail(null);
      return;
    }
    void loadDetail(selectedId).catch((e) =>
      setError(e instanceof Error ? e.message : "加载文档失败"),
    );
  }, [selectedId, loadDetail]);

  useEffect(() => {
    if (!selectedId || detail?.status !== "published") return;
    if (!ingestJob || !["pending", "running"].includes(ingestJob.status)) return;
    const timer = window.setInterval(() => {
      void getIngestStatus(selectedId)
        .then(setIngestJob)
        .catch(() => undefined);
    }, 3000);
    return () => window.clearInterval(timer);
  }, [selectedId, detail?.status, ingestJob]);

  async function handleSelectDoc(id: string) {
    setSelectedNav("knowledge");
    const doc = documents.find((d) => d.id === id);
    if (doc?.folder_id && doc.folder_id !== currentFolderId) {
      setCurrentFolderId(doc.folder_id);
      try {
        await refreshAll(doc.folder_id);
      } catch {
        /* keep selection */
      }
    }
    setSelectedId(id);
    setError(null);
  }

  async function handleOpenReviewDoc(id: string) {
    setSelectedNav("reviewTasks");
    setSelectedId(id);
    setError(null);
  }

  function handleBackToReviewTasks() {
    setSelectedId(null);
    setSelectedNav("reviewTasks");
    setDetail(null);
  }

  async function handleSelectFolder(id: string | null) {
    setCurrentFolderId(id);
    setSelectedId(null);
    setError(null);
    try {
      await refreshAll(id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "加载文件夹失败");
    }
  }

  async function handleCreateDoc() {
    if (!currentFolderId) {
      setError("请先选择一个知识库");
      return;
    }
    setAddFilesOpen(true);
  }

  async function handleAddFilesSubmit(payload: AddFilesPayload) {
    if (!currentFolderId) {
      setError("请先选择一个知识库");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      let lastId: string | null = null;
      for (const file of payload.files) {
        const docTitle =
          payload.mode === "file"
            ? payload.title
            : file.name.split(/[/\\]/).pop() || file.name;
        const doc = await createDocument();
        await moveDocumentToFolder(doc.id, currentFolderId);
        await saveDocument(doc.id, { title: docTitle, tag: payload.tag });
        await uploadDocumentFile(doc.id, file);
        if (payload.action === "review") {
          await submitForReview(doc.id, {
            reviewer_user_id: payload.reviewer_user_id ?? null,
            review_comment: payload.review_comment,
          });
        }
        lastId = doc.id;
      }
      setAddFilesOpen(false);
      await refreshAll(currentFolderId);
      if (payload.action === "review") {
        setSelectedId(null);
      } else if (payload.mode === "file" && lastId) {
        setSelectedId(lastId);
      } else {
        setSelectedId(null);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "上传失败");
    } finally {
      setBusy(false);
    }
  }

  async function handleCreateFolder(
    parentId: string | null,
    meta?: {
      name: string;
      description?: string;
      visibility?: FolderVisibility;
    },
  ) {
    // Nested folders (non-root) keep a simple prompt; root KBs use the modal form.
    let name = meta?.name;
    let description = meta?.description ?? "";
    let visibility: FolderVisibility = meta?.visibility ?? "private";
    if (!name) {
      if (parentId == null) {
        setCreateKbOpen(true);
        return;
      }
      const prompted = window.prompt("请输入文件夹名称");
      if (!prompted?.trim()) return;
      name = prompted.trim();
    }
    setBusy(true);
    setError(null);
    try {
      const created = await createFolder({
        name,
        parent_id: parentId,
        description,
        visibility,
      });
      setCreateKbOpen(false);
      setSelectedNav("knowledge");
      setCurrentFolderId(created.folder_id);
      setSelectedId(null);
      await refreshAll(created.folder_id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "创建知识库失败");
    } finally {
      setBusy(false);
    }
  }

  async function handleAddMember(values: AddMemberValues) {
    if (!canManageMembers) {
      setError("只有管理员或所有者可以添加成员");
      setAddMemberOpen(false);
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const created = await createTenantMember(values);
      setCreatedMemberPassword(created.temporary_password);
      setAddMemberOpen(false);
      setSelectedNav("permissions");
      setMembers(await listTenantMembers());
    } catch (e) {
      setError(e instanceof Error ? e.message : "添加成员失败");
    } finally {
      setBusy(false);
    }
  }

  async function handleRenameFolder(id: string, currentName: string) {
    const name = window.prompt("修改知识库名称", currentName);
    if (!name?.trim() || name.trim() === currentName) return;
    setBusy(true);
    setError(null);
    try {
      await renameFolder(id, name.trim());
      await refreshAll(currentFolderId);
    } catch (e) {
      setError(e instanceof Error ? e.message : "修改知识库失败");
    } finally {
      setBusy(false);
    }
  }

  async function handleMoveFolder(id: string) {
    const target = pickTargetFolder(tree, id, "将文件夹移动到：");
    if (target === undefined) return;
    setBusy(true);
    setError(null);
    try {
      await moveFolder(id, target);
      await refreshAll(currentFolderId);
    } catch (e) {
      setError(e instanceof Error ? e.message : "移动文件夹失败");
    } finally {
      setBusy(false);
    }
  }

  async function handleDeleteFolder(id: string, currentName?: string) {
    const label = currentName?.trim() || "该知识库";
    if (
      !window.confirm(
        `确定删除知识库「${label}」吗？仅当知识库为空（无文件、无子文件夹）时可删除。`,
      )
    ) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await deleteFolder(id);
      const nextFolder = currentFolderId === id ? null : currentFolderId;
      setCurrentFolderId(nextFolder);
      if (selectedId) {
        const doc = documents.find((d) => d.id === selectedId);
        if (doc?.folder_id === id) setSelectedId(null);
      }
      await refreshAll(nextFolder);
    } catch (e) {
      setError(e instanceof Error ? e.message : "删除知识库失败");
    } finally {
      setBusy(false);
    }
  }

  async function handleRenameDocument(docId: string, currentName: string) {
    const name = window.prompt("重命名文件", currentName);
    if (!name?.trim() || name.trim() === currentName) return;
    setBusy(true);
    setError(null);
    try {
      await saveDocument(docId, { title: name.trim() });
      if (selectedId === docId) {
        await loadDetail(docId);
      }
      await refreshAll(currentFolderId);
    } catch (e) {
      setError(e instanceof Error ? e.message : "重命名文件失败");
    } finally {
      setBusy(false);
    }
  }

  async function handleDeleteDocument(docId: string, currentName: string) {
    if (!window.confirm(`确定删除文件「${currentName || "未命名文档"}」吗？`)) return;
    setBusy(true);
    setError(null);
    try {
      await deleteDocument(docId);
      if (selectedId === docId) {
        setSelectedId(null);
      }
      await refreshAll(currentFolderId);
    } catch (e) {
      setError(e instanceof Error ? e.message : "删除文件失败");
    } finally {
      setBusy(false);
    }
  }

  async function handleDeleteDocuments(
    items: { id: string; name: string }[],
  ) {
    if (items.length === 0) return;
    const label =
      items.length === 1
        ? `确定删除文件「${items[0].name}」吗？`
        : `确定删除所选的 ${items.length} 个文件吗？`;
    if (!window.confirm(label)) return;
    setBusy(true);
    setError(null);
    try {
      for (const item of items) {
        await deleteDocument(item.id);
        if (selectedId === item.id) setSelectedId(null);
      }
      await refreshAll(currentFolderId);
    } catch (e) {
      setError(e instanceof Error ? e.message : "删除文件失败");
    } finally {
      setBusy(false);
    }
  }

  async function handleDownloadDocument(docId: string, currentName: string) {
    setBusy(true);
    setError(null);
    try {
      await downloadDocument(docId, currentName || "download");
    } catch (e) {
      setError(e instanceof Error ? e.message : "下载失败");
    } finally {
      setBusy(false);
    }
  }

  async function handleMoveDocument(docId: string) {
    const target = pickTargetFolder(tree, null, "将文档移动到：");
    if (target === undefined) return;
    setBusy(true);
    setError(null);
    try {
      await moveDocumentToFolder(docId, target);
      await refreshAll(currentFolderId);
    } catch (e) {
      setError(e instanceof Error ? e.message : "移动文档失败");
    } finally {
      setBusy(false);
    }
  }

  async function handleSave() {
    if (!selectedId) return;
    setBusy(true);
    setError(null);
    try {
      const doc = await saveDocument(selectedId, {
        title,
        tag: tag || undefined,
      });
      setDetail(doc);
      await refreshAll(currentFolderId);
    } catch (e) {
      setError(e instanceof Error ? e.message : "保存失败");
    } finally {
      setBusy(false);
    }
  }

  function validateForReview(): string[] {
    const errs: string[] = [];
    if (!title.trim()) errs.push("请填写文档标题");
    if (!tag) errs.push("请选择文档分类");
    if (!detail?.file_name) errs.push("请至少上传一份文档");
    return errs;
  }

  async function handleSubmitReview() {
    if (!selectedId) return;
    const errs = validateForReview();
    if (errs.length) {
      setValidationErrors(errs);
      return;
    }
    setBusy(true);
    setError(null);
    setWarning(null);
    setValidationErrors([]);
    try {
      await saveDocument(selectedId, { title, tag });
      const doc = await submitForReview(selectedId);
      setDetail(doc);
      await refreshAll(currentFolderId);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "提交失败";
      setValidationErrors([msg]);
    } finally {
      setBusy(false);
    }
  }

  async function handleCompleteReview(values: ReviewDecisionValues) {
    if (!selectedId) return;
    const fromReviewTasks = selectedNav === "reviewTasks";
    setBusy(true);
    setError(null);
    setWarning(null);
    try {
      const doc = await completeDocumentReview(selectedId, {
        decision: values.decision,
        review_comment: values.reviewComment || undefined,
      });
      setDetail(doc);
      if (doc.warning) setWarning(doc.warning);
      if (values.decision !== "approve") {
        setIngestJob(null);
      }
      await refreshAll(currentFolderId);
      if (fromReviewTasks) {
        setReviewTasks(await listReviewTasks());
        handleBackToReviewTasks();
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "审核失败");
      try {
        await loadDetail(selectedId);
        await refreshAll(currentFolderId);
      } catch {
        /* keep error */
      }
      throw e;
    } finally {
      setBusy(false);
    }
  }

  async function handlePublish() {
    if (!selectedId) return;
    setBusy(true);
    setError(null);
    setWarning(null);
    try {
      const doc = await publishDocument(selectedId);
      setDetail(doc);
      if (doc.warning) setWarning(doc.warning);
      const job = await getIngestStatus(selectedId);
      setIngestJob(job);
      if (job?.warning) setWarning(job.warning);
      await refreshAll(currentFolderId);
      if (selectedNav === "reviewTasks") {
        setReviewTasks(await listReviewTasks());
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "发布失败");
      try {
        await loadDetail(selectedId);
        await refreshAll(currentFolderId);
      } catch {
        /* keep error */
      }
    } finally {
      setBusy(false);
    }
  }

  async function handlePublishFromList(id: string, name: string) {
    const confirmed = window.confirm(`确认发布「${name}」？\n\n发布后将写入知识库，供 AI 问答检索。`);
    if (!confirmed) return;
    setBusy(true);
    setError(null);
    setWarning(null);
    try {
      const doc = await publishDocument(id);
      if (doc.warning) setWarning(doc.warning);
      if (selectedId === id) {
        setDetail(doc);
        const job = await getIngestStatus(id);
        setIngestJob(job);
        if (job?.warning) setWarning(job.warning);
      }
      await refreshAll(currentFolderId);
    } catch (e) {
      setError(e instanceof Error ? e.message : "发布失败");
      try {
        await refreshAll(currentFolderId);
      } catch {
        /* keep error */
      }
    } finally {
      setBusy(false);
    }
  }

  async function handleBulkApprove(items: { id: string; name: string }[]) {
    if (items.length === 0) return;
    const names = items.map((item) => item.name).join("\n");
    const confirmed = window.confirm(
      `确认批量审核通过以下 ${items.length} 个文件？\n通过后状态变为待发布。\n\n${names}`,
    );
    if (!confirmed) return;

    setBusy(true);
    setError(null);
    setWarning(null);
    try {
      for (const item of items) {
        await completeDocumentReview(item.id, { decision: "approve" });
      }
      setReviewTasks(await listReviewTasks());
      await refreshAll(currentFolderId);
    } catch (e) {
      setError(e instanceof Error ? e.message : "批量审核失败");
    } finally {
      setBusy(false);
    }
  }

  async function handleNewVersion() {
    if (!selectedId) return;
    setBusy(true);
    setError(null);
    try {
      const doc = await newDocumentVersion(selectedId);
      setDetail(doc);
      setSelectedId(doc.id);
      setTitle(doc.title);
      setTag(doc.tag);
      setIngestJob(null);
      await refreshAll(currentFolderId);
    } catch (e) {
      setError(e instanceof Error ? e.message : "创建新版本失败");
    } finally {
      setBusy(false);
    }
  }

  async function handleUploadFile(file: File) {
    if (!selectedId) return;
    setBusy(true);
    setError(null);
    try {
      await saveDocument(selectedId, { title, tag: tag || undefined });
      if (!isAllowedFile(file.name)) {
        throw new Error(`${fileTypeRejectMessage(file.name)}：${file.name}`);
      }
      if (file.size > MAX_FILE_BYTES) {
        throw new Error(`文件超过 20MB：${file.name}`);
      }
      await uploadDocumentFile(selectedId, file);
      await loadDetail(selectedId, { preserveForm: true });
      await refreshAll(currentFolderId);
    } catch (e) {
      setError(e instanceof Error ? e.message : "上传失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="chat-shell">
      <DocSidebar
        search={search}
        selectedNav={selectedNav}
        selectedPermissionSection={selectedPermissionSection}
        knowledgeBases={knowledgeBases}
        currentFolderId={currentFolderId}
        busy={busy}
        canReviewTasks={canReviewTasks}
        onSearch={setSearch}
        onSelectPermissionSection={setSelectedPermissionSection}
        onSelectNav={(nav) => {
          setSelectedNav(nav);
          setSelectedId(null);
          if (nav === "knowledge") {
            void handleSelectFolder(null);
          }
        }}
        onSelectKnowledgeBase={(id) => {
          setSelectedNav("knowledge");
          void handleSelectFolder(id);
        }}
        onCreateKnowledgeBase={() => setCreateKbOpen(true)}
        onRenameKnowledgeBase={(id, name) => void handleRenameFolder(id, name)}
        onDeleteKnowledgeBase={(id, name) => void handleDeleteFolder(id, name)}
      />
      <CreateKnowledgeBaseModal
        open={createKbOpen}
        busy={busy}
        onClose={() => {
          if (!busy) setCreateKbOpen(false);
        }}
        onSubmit={(values) =>
          handleCreateFolder(null, {
            name: values.name,
            description: values.description,
            visibility: values.visibility,
          })
        }
      />
      <AddFilesModal
        open={addFilesOpen}
        busy={busy}
        onClose={() => {
          if (!busy) setAddFilesOpen(false);
        }}
        reviewers={reviewers}
        onSubmit={(payload) => handleAddFilesSubmit(payload)}
      />
      <AddMemberModal
        open={addMemberOpen}
        busy={busy}
        onClose={() => {
          if (!busy) setAddMemberOpen(false);
        }}
        onSubmit={(values) => handleAddMember(values)}
      />
      <div className="doc-main-wrap">
        {error ? (
          <p className="doc-alert" role="alert">
            {error}
          </p>
        ) : null}
        {warning ? (
          <p className="doc-alert doc-alert-warning" role="status">
            {warning}
          </p>
        ) : null}
        {selectedNav === "home" ? (
          <div className="chat-main doc-main kb-browser">
            <p className="kb-section-eyebrow">主页</p>
            <h2 className="kb-browser-title">主页</h2>
            <p className="kb-browser-empty">这里可以放首页概览内容。</p>
          </div>
        ) : selectedNav === "reviewTasks" ? (
          viewingReviewDoc ? (
            detail && detail.id === selectedId ? (
              <ReviewTaskDetail
                doc={detail}
                uploader={activeReviewTask?.uploader}
                reviewer={activeReviewTask?.reviewer}
                reviewedAt={activeReviewTask?.reviewed_at}
                reviewComment={activeReviewTask?.review_comment}
                busy={busy}
                onBack={handleBackToReviewTasks}
                onCompleteReview={handleCompleteReview}
              />
            ) : (
              <div className="chat-main doc-main kb-browser">
                <button type="button" className="kb-crumb" onClick={handleBackToReviewTasks}>
                  ← 返回待审核任务
                </button>
                <p className="kb-browser-empty">正在加载文件详情…</p>
              </div>
            )
          ) : (
            <FolderBrowser
              currentFolderId={null}
              layer={null}
              tree={tree}
              busy={busy}
              titleOverride="待审核任务"
              subtitleOverride="所有提交给当前账号审核的文件"
              documentsOverride={reviewTasks}
              emptyTextOverride="暂无待审核文件"
              searchPlaceholder="搜索文件名或上传人"
              hideCreateActions
              hideRowActions
              selectionActionLabel="批量审核通过"
              onSelectionAction={(items) => void handleBulkApprove(items)}
              onCreateDoc={() => undefined}
              onCreateFolder={() => undefined}
              onOpenDoc={(id) => void handleOpenReviewDoc(id)}
              onRenameDoc={() => undefined}
              onDownloadDoc={() => undefined}
              onDeleteDoc={() => undefined}
              onDeleteDocs={() => undefined}
            />
          )
        ) : selectedNav === "permissions" ? (
          <div className="chat-main doc-main kb-browser">
            <p className="kb-section-eyebrow">权限管理</p>
            <h2 className="kb-browser-title">
              {selectedPermissionSection === "members" ? "成员管理" : "权限管理"}
            </h2>
            <div style={{ display: "flex", justifyContent: "space-between", gap: "1rem", alignItems: "center" }}>
              <p className="kb-browser-empty" style={{ margin: 0 }}>
                {canManageMembers
                  ? "可添加成员，并为新成员分配默认密码与角色。"
                  : "当前账号可查看权限区，但只有管理员或所有者可以添加成员。"}
              </p>
              {canManageMembers ? (
                <button type="button" className="btn primary" disabled={busy} onClick={() => setAddMemberOpen(true)}>
                  添加成员
                </button>
              ) : null}
            </div>
            {createdMemberPassword ? (
              <p className="doc-alert doc-alert-warning" role="status" style={{ marginTop: "1rem" }}>
                新成员的系统默认密码：<code>{createdMemberPassword}</code>。请尽快安全地告知对方，首次登录后会强制修改。
              </p>
            ) : null}
            <div style={{ marginTop: "1rem", overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse" }}>
                <thead>
                  <tr>
                    <th align="left">成员名</th>
                    <th align="left">邮箱</th>
                    <th align="left">角色</th>
                  </tr>
                </thead>
                <tbody>
                  {members.map((member) => (
                    <tr key={member.member_id}>
                      <td style={{ padding: "0.5rem 0" }}>{member.member_name}</td>
                      <td>{member.email}</td>
                      <td>{member.role === "admin" ? "管理员" : member.role === "owner" ? "所有者" : "普通用户"}</td>
                    </tr>
                  ))}
                  {members.length === 0 ? (
                    <tr>
                      <td colSpan={3} className="kb-browser-empty" style={{ paddingTop: "1rem" }}>
                        暂无成员
                      </td>
                    </tr>
                  ) : null}
                </tbody>
              </table>
            </div>
          </div>
        ) : viewingDoc ? (
          <>
            <nav className="kb-breadcrumb kb-breadcrumb-main" aria-label="面包屑">
              <button
                type="button"
                className="kb-crumb"
                onClick={() => void handleSelectFolder(null)}
              >
                知识库
              </button>
              {breadcrumb.map((node) => (
                <span key={node.folder_id} className="kb-crumb-wrap">
                  <span className="kb-crumb-sep" aria-hidden>
                    /
                  </span>
                  <button
                    type="button"
                    className="kb-crumb"
                    onClick={() => void handleSelectFolder(node.folder_id)}
                  >
                    {node.name}
                  </button>
                </span>
              ))}
              <span className="kb-crumb-wrap">
                <span className="kb-crumb-sep" aria-hidden>
                  /
                </span>
                <span className="kb-crumb current">
                  {title.trim() || detail?.title.trim() || "未命名文档"}
                </span>
              </span>
            </nav>
            <DocEditor
              doc={detail}
              title={title}
              tag={tag}
              validationErrors={validationErrors}
              busy={busy}
              ingestJob={ingestJob}
              onTitleChange={setTitle}
              onTagChange={setTag}
              onSave={() => void handleSave()}
              onSubmitReview={() => void handleSubmitReview()}
              onPublish={() => void handlePublish()}
              onNewVersion={() => void handleNewVersion()}
              onUploadFile={(file) => void handleUploadFile(file)}
            />
          </>
        ) : (
          <FolderBrowser
            currentFolderId={currentFolderId}
            layer={layer}
            tree={tree}
            busy={busy}
            onOpenDoc={(id) => void handleSelectDoc(id)}
            onCreateDoc={() => void handleCreateDoc()}
            onCreateFolder={() => setCreateKbOpen(true)}
            onRenameDoc={(id, name) => void handleRenameDocument(id, name)}
            onDownloadDoc={(id, name) => void handleDownloadDocument(id, name)}
            onDeleteDoc={(id, name) => void handleDeleteDocument(id, name)}
            onDeleteDocs={(items) => void handleDeleteDocuments(items)}
            onPublishDoc={(id, name) => void handlePublishFromList(id, name)}
          />
        )}
      </div>
    </div>
  );
}
