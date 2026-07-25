"use client";

import { useCallback, useEffect, useState } from "react";

import { DocEditor } from "@/components/admin/DocEditor";
import { DocSidebar } from "@/components/admin/DocSidebar";
import {
  createDocument,
  getDocument,
  getIngestStatus,
  listDocuments,
  newDocumentVersion,
  publishDocument,
  saveDocument,
  submitForReview,
  uploadDocumentFile,
} from "@/lib/api";
import type { DocDetail, DocSummary, DocTag, IngestJobStatus } from "@/lib/documents";
import { fileTypeRejectMessage, isAllowedFile, MAX_FILE_BYTES } from "@/lib/documents";

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
  const [warning, setWarning] = useState<string | null>(null);
  const [validationErrors, setValidationErrors] = useState<string[]>([]);
  const [ingestJob, setIngestJob] = useState<IngestJobStatus | null>(null);

  const refreshList = useCallback(async () => {
    const items = await listDocuments();
    setDocuments(items);
    return items;
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
    if (!ingestJob || !["pending", "running"].includes(ingestJob.status)) return;
    const timer = window.setInterval(() => {
      void getIngestStatus(selectedId)
        .then(setIngestJob)
        .catch(() => undefined);
    }, 3000);
    return () => window.clearInterval(timer);
  }, [selectedId, detail?.status, ingestJob]);

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
    setWarning(null);
    try {
      const doc = await publishDocument(selectedId);
      setDetail(doc);
      if (doc.warning) {
        setWarning(doc.warning);
      }
      const job = await getIngestStatus(selectedId);
      setIngestJob(job);
      if (job?.warning) {
        setWarning(job.warning);
      }
      await refreshList();
    } catch (e) {
      const msg = e instanceof Error ? e.message : "发布失败";
      setError(msg);
      // 409 duplicate (or other publish reject): reload so status reflects draft
      try {
        await loadDetail(selectedId);
        await refreshList();
      } catch {
        /* keep error banner */
      }
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
      await refreshList();
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
        {warning ? (
          <p className="doc-alert doc-alert-warning" role="status">
            {warning}
          </p>
        ) : null}
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
      </div>
    </div>
  );
}
