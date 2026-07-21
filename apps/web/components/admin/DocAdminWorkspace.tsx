"use client";

import { useCallback, useEffect, useState } from "react";

import { DocEditor } from "@/components/admin/DocEditor";
import { DocSidebar } from "@/components/admin/DocSidebar";
import {
  createDocument,
  getDocument,
  getIndexStatus,
  listDocuments,
  newDocumentVersion,
  publishDocument,
  saveDocument,
  submitForReview,
  uploadDocumentFile,
} from "@/lib/api";
import type { DocDetail, DocSummary, DocTag, IndexJobStatus } from "@/lib/documents";
import { isAllowedFile, MAX_FILE_BYTES } from "@/lib/documents";

export function DocAdminWorkspace() {
  const [documents, setDocuments] = useState<DocSummary[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<DocDetail | null>(null);
  const [title, setTitle] = useState("");
  const [tag, setTag] = useState("");
  const [tagFilter, setTagFilter] = useState<DocTag | "all">("all");
  const [search, setSearch] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [validationErrors, setValidationErrors] = useState<string[]>([]);
  const [indexJob, setIndexJob] = useState<IndexJobStatus | null>(null);

  const refreshList = useCallback(async () => {
    const items = await listDocuments();
    setDocuments(items);
    return items;
  }, []);

  const loadDetail = useCallback(async (id: string) => {
    const doc = await getDocument(id);
    setDetail(doc);
    setTitle(doc.title);
    setTag(doc.tag);
    setValidationErrors([]);
    if (doc.status === "published") {
      const job = await getIndexStatus(id);
      setIndexJob(job);
    } else {
      setIndexJob(null);
    }
  }, []);

  useEffect(() => {
    void refreshList().catch((e) =>
      setError(e instanceof Error ? e.message : "加载失败"),
    );
  }, [refreshList]);

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
    if (!indexJob || !["pending", "running"].includes(indexJob.status)) return;
    const timer = window.setInterval(() => {
      void getIndexStatus(selectedId)
        .then(setIndexJob)
        .catch(() => undefined);
    }, 3000);
    return () => window.clearInterval(timer);
  }, [selectedId, detail?.status, indexJob]);

  async function handleSelect(id: string) {
    setSelectedId(id);
    setError(null);
  }

  async function handleCreate() {
    setBusy(true);
    setError(null);
    try {
      const doc = await createDocument();
      await refreshList();
      setSelectedId(doc.id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "创建失败");
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
      await refreshList();
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
    if (!detail?.files.length) errs.push("请至少上传一份文档");
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
    setValidationErrors([]);
    try {
      await saveDocument(selectedId, { title, tag });
      const doc = await submitForReview(selectedId);
      setDetail(doc);
      await refreshList();
    } catch (e) {
      const msg = e instanceof Error ? e.message : "提交失败";
      setValidationErrors([msg]);
    } finally {
      setBusy(false);
    }
  }

  async function handlePublish() {
    if (!selectedId) return;
    setBusy(true);
    setError(null);
    try {
      const doc = await publishDocument(selectedId);
      setDetail(doc);
      const job = await getIndexStatus(selectedId);
      setIndexJob(job);
      await refreshList();
    } catch (e) {
      setError(e instanceof Error ? e.message : "发布失败");
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
      await refreshList();
    } catch (e) {
      setError(e instanceof Error ? e.message : "创建新版本失败");
    } finally {
      setBusy(false);
    }
  }

  async function handleUploadFiles(files: FileList) {
    if (!selectedId) return;
    setBusy(true);
    setError(null);
    try {
      for (const file of Array.from(files)) {
        if (!isAllowedFile(file.name)) {
          throw new Error(`不支持的文件类型：${file.name}`);
        }
        if (file.size > MAX_FILE_BYTES) {
          throw new Error(`文件超过 20MB：${file.name}`);
        }
        await uploadDocumentFile(selectedId, file);
      }
      await loadDetail(selectedId);
      await refreshList();
    } catch (e) {
      setError(e instanceof Error ? e.message : "上传失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="chat-shell">
      <DocSidebar
        documents={documents}
        tagFilter={tagFilter}
        search={search}
        selectedId={selectedId}
        busy={busy}
        onTagFilter={setTagFilter}
        onSearch={setSearch}
        onSelect={(id) => void handleSelect(id)}
        onCreate={() => void handleCreate()}
      />
      <div className="doc-main-wrap">
        {error ? (
          <p className="doc-alert" role="alert">
            {error}
          </p>
        ) : null}
        <DocEditor
          doc={detail}
          title={title}
          tag={tag}
          validationErrors={validationErrors}
          busy={busy}
          indexJob={indexJob}
          onTitleChange={setTitle}
          onTagChange={setTag}
          onSave={() => void handleSave()}
          onSubmitReview={() => void handleSubmitReview()}
          onPublish={() => void handlePublish()}
          onNewVersion={() => void handleNewVersion()}
          onUploadFiles={(files) => void handleUploadFiles(files)}
        />
      </div>
    </div>
  );
}
