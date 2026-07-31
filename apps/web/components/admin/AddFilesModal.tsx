"use client";

import {
  useEffect,
  useId,
  useRef,
  useState,
  type DragEvent,
} from "react";

import {
  TAG_OPTIONS,
  fileTypeRejectMessage,
  formatBytes,
  formatVersionDisplay,
  isAllowedFile,
  MAX_FILE_BYTES,
  type DocTag,
} from "@/lib/documents";
import { IngestJobStatusCard } from "@/components/admin/IngestJobStatusCard";
import type { ReviewerOption } from "@/lib/api";

export type AddFilesPayload = {
  mode: "file" | "folder";
  tag: string;
  /** Single-file mode only; ignored for folder. */
  title: string;
  files: File[];
  action: "draft" | "review";
  reviewer_user_id?: string;
  review_comment?: string;
};

type Props = {
  open: boolean;
  busy?: boolean;
  reviewers: ReviewerOption[];
  onClose: () => void;
  onSubmit: (payload: AddFilesPayload) => void | Promise<void>;
};

type FileSystemEntryLike = {
  isFile: boolean;
  isDirectory: boolean;
  name: string;
  file?: (
    success: (file: File) => void,
    error?: (err: DOMException) => void,
  ) => void;
  createReader?: () => {
    readEntries: (
      success: (entries: FileSystemEntryLike[]) => void,
      error?: (err: DOMException) => void,
    ) => void;
  };
};

function fileBaseName(name: string): string {
  return name.split(/[/\\]/).pop() || name;
}

function readAllDirectoryEntries(
  reader: NonNullable<FileSystemEntryLike["createReader"]> extends () => infer R
    ? R
    : never,
): Promise<FileSystemEntryLike[]> {
  return new Promise((resolve, reject) => {
    const all: FileSystemEntryLike[] = [];
    const readBatch = () => {
      reader.readEntries(
        (entries) => {
          if (!entries.length) {
            resolve(all);
            return;
          }
          all.push(...entries);
          readBatch();
        },
        reject,
      );
    };
    readBatch();
  });
}

async function collectFilesFromEntry(
  entry: FileSystemEntryLike,
  pathPrefix = "",
): Promise<File[]> {
  if (entry.isFile && entry.file) {
    const file = await new Promise<File>((resolve, reject) => {
      entry.file!(resolve, reject);
    });
    const relative = pathPrefix
      ? `${pathPrefix}${fileBaseName(file.name)}`
      : fileBaseName(file.name);
    Object.defineProperty(file, "webkitRelativePath", {
      configurable: true,
      value: relative,
    });
    return [file];
  }
  if (entry.isDirectory && entry.createReader) {
    const reader = entry.createReader();
    const children = await readAllDirectoryEntries(reader);
    const nextPrefix = `${pathPrefix}${entry.name}/`;
    const nested = await Promise.all(
      children.map((child) => collectFilesFromEntry(child, nextPrefix)),
    );
    return nested.flat();
  }
  return [];
}

async function collectFilesFromDataTransfer(
  dt: DataTransfer,
): Promise<{ files: File[]; fromDirectory: boolean }> {
  const items = Array.from(dt.items || []);
  if (items.length > 0 && typeof items[0].webkitGetAsEntry === "function") {
    let fromDirectory = false;
    const groups = await Promise.all(
      items.map(async (item) => {
        const entry = item.webkitGetAsEntry?.() as FileSystemEntryLike | null;
        if (!entry) {
          const f = item.getAsFile();
          return f ? [f] : [];
        }
        if (entry.isDirectory) fromDirectory = true;
        return collectFilesFromEntry(entry);
      }),
    );
    return { files: groups.flat(), fromDirectory };
  }
  return {
    files: Array.from(dt.files || []),
    fromDirectory: false,
  };
}

function IconFile() {
  return (
    <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden>
      <path
        fill="currentColor"
        d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6zm1 7V3.5L19.5 9H15zM8 13h8v1.5H8V13zm0 3h8v1.5H8V16zm0-6h5v1.5H8V10z"
      />
    </svg>
  );
}

function IconFolder() {
  return (
    <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden>
      <path
        fill="currentColor"
        d="M10 4H4a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-8l-2-2zm1 7v2.5H8.5v1.5H11V17h1.5v-2H15v-1.5h-2.5V11H11z"
      />
    </svg>
  );
}

function IconUpload() {
  return (
    <svg viewBox="0 0 24 24" width="40" height="40" aria-hidden>
      <path
        fill="currentColor"
        d="M11 16h2V9.8l2.1 2.1 1.4-1.4L12 6l-4.5 4.5 1.4 1.4L11 9.8V16zm-6 4h14v-2H5v2z"
      />
    </svg>
  );
}

export function AddFilesModal({
  open,
  busy = false,
  reviewers,
  onClose,
  onSubmit,
}: Props) {
  const formId = useId();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const folderInputRef = useRef<HTMLInputElement>(null);
  const [uploadMode, setUploadMode] = useState<"file" | "folder">("file");
  const [files, setFiles] = useState<File[]>([]);
  const [title, setTitle] = useState("");
  const [tag, setTag] = useState<DocTag | "">("");
  const [reviewFormOpen, setReviewFormOpen] = useState(false);
  const [reviewerUserId, setReviewerUserId] = useState("");
  const [reviewComment, setReviewComment] = useState("");
  const [localError, setLocalError] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);

  useEffect(() => {
    if (!open) return;
    setUploadMode("file");
    setFiles([]);
    setTitle("");
    setTag("");
    setReviewFormOpen(false);
    setReviewerUserId("");
    setReviewComment("");
    setLocalError(null);
    setDragOver(false);
  }, [open]);

  useEffect(() => {
    const el = folderInputRef.current;
    if (!el) return;
    el.setAttribute("webkitdirectory", "");
    el.setAttribute("directory", "");
  }, [open, uploadMode]);

  useEffect(() => {
    if (!open) return;
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape" && !busy) onClose();
    }
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [open, busy, onClose]);

  if (!open) return null;

  function applyPickedFiles(list: File[], asMode: "file" | "folder") {
    if (list.length === 0) return;
    const accepted: File[] = [];
    const rejected: string[] = [];
    for (const file of list) {
      const name = fileBaseName(file.name);
      if (name.startsWith(".")) continue;
      if (!isAllowedFile(name)) {
        rejected.push(`${name}（${fileTypeRejectMessage(name)}）`);
        continue;
      }
      if (file.size > MAX_FILE_BYTES) {
        rejected.push(`${name}（超过 50MB）`);
        continue;
      }
      accepted.push(file);
    }
    if (accepted.length === 0) {
      setLocalError(
        rejected.length > 0
          ? `没有可上传的文件：${rejected.slice(0, 3).join("；")}`
          : "没有可上传的文件",
      );
      return;
    }
    setUploadMode(asMode);
    setFiles(accepted);
    if (asMode === "file" && accepted.length === 1) {
      setTitle(fileBaseName(accepted[0].name));
    } else {
      setTitle("");
    }
    setLocalError(
      rejected.length > 0
        ? `已跳过 ${rejected.length} 个不支持的文件`
        : null,
    );
  }

  function switchMode(next: "file" | "folder") {
    setUploadMode(next);
    setFiles([]);
    setTitle("");
    setLocalError(null);
  }

  async function handleDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setDragOver(false);
    if (busy) return;
    try {
      const { files: dropped, fromDirectory } =
        await collectFilesFromDataTransfer(e.dataTransfer);
      if (uploadMode === "folder") {
        if (!fromDirectory && dropped.length <= 1) {
          setLocalError("当前为文件夹模式，请拖入文件夹");
          return;
        }
        applyPickedFiles(dropped, "folder");
        return;
      }
      if (fromDirectory) {
        setLocalError("当前为文件模式，请切换到「文件夹」后再拖入文件夹");
        return;
      }
      applyPickedFiles(dropped, dropped.length > 1 ? "folder" : "file");
      if (dropped.length > 1) setUploadMode("folder");
    } catch {
      setLocalError("读取拖拽内容失败，请重试");
    }
  }

  function handleZoneClick() {
    if (busy) return;
    if (uploadMode === "folder") {
      folderInputRef.current?.click();
      return;
    }
    fileInputRef.current?.click();
  }

  function buildPayload(action: "draft" | "review"): AddFilesPayload | null {
    if (files.length === 0) {
      setLocalError(
        uploadMode === "folder"
          ? "请点击虚线区域选择文件夹，或将文件夹拖入此处"
          : "请点击虚线区域选择文件，或拖拽文件到此处",
      );
      return null;
    }
    if (!tag) {
      setLocalError("请选择文档分类");
      return null;
    }
    const singleFile = uploadMode === "file" && files.length === 1;
    if (singleFile && !title.trim()) {
      setLocalError("请填写文档标题");
      return null;
    }
    setLocalError(null);
    return {
      mode: singleFile ? "file" : "folder",
      tag,
      title: title.trim(),
      files,
      action,
      reviewer_user_id: action === "review" ? reviewerUserId || undefined : undefined,
      review_comment: action === "review" ? reviewComment.trim() || undefined : undefined,
    };
  }

  async function handleAction(action: "draft" | "review") {
    if (action === "review" && !reviewFormOpen) {
      setReviewFormOpen(true);
      return;
    }
    const payload = buildPayload(action);
    if (!payload) return;
    if (action === "review" && !reviewerUserId) {
      setLocalError("请选择审核人");
      return;
    }
    await onSubmit(payload);
  }

  const showTitle = uploadMode === "file" && files.length <= 1;

  return (
    <div
      className="kb-modal-backdrop"
      role="presentation"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget && !busy) onClose();
      }}
    >
      <div
        className="kb-modal kb-modal-wide"
        role="dialog"
        aria-modal="true"
        aria-labelledby={`${formId}-title`}
      >
        <header className="kb-modal-header">
          <h2 id={`${formId}-title`} className="kb-modal-title">
            新增文件
          </h2>
          <button
            type="button"
            className="kb-modal-close"
            aria-label="关闭"
            disabled={busy}
            onClick={onClose}
          >
            ×
          </button>
        </header>

        <div className="kb-modal-form">
          <div className="kb-modal-field">
            <div className="kb-upload-mode-tabs" role="tablist" aria-label="上传类型">
              <button
                type="button"
                role="tab"
                aria-selected={uploadMode === "file"}
                className={`kb-upload-mode-tab${uploadMode === "file" ? " active" : ""}`}
                disabled={busy}
                onClick={() => switchMode("file")}
              >
                <IconFile />
                <span>文件</span>
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={uploadMode === "folder"}
                className={`kb-upload-mode-tab${uploadMode === "folder" ? " active" : ""}`}
                disabled={busy}
                onClick={() => switchMode("folder")}
              >
                <IconFolder />
                <span>文件夹</span>
              </button>
            </div>

            <input
              ref={fileInputRef}
              type="file"
              className="doc-file-input"
              accept=".txt,.md,.pdf,.docx,.pptx,.xlsx"
              multiple
              onChange={(e) => {
                const picked = Array.from(e.target.files || []);
                applyPickedFiles(
                  picked,
                  picked.length > 1 ? "folder" : "file",
                );
                e.target.value = "";
              }}
            />
            <input
              ref={folderInputRef}
              type="file"
              className="doc-file-input"
              multiple
              onChange={(e) => {
                applyPickedFiles(Array.from(e.target.files || []), "folder");
                e.target.value = "";
              }}
            />

            <div
              className={`kb-dropzone kb-dropzone-card${dragOver ? " dragover" : ""}`}
              role="button"
              tabIndex={0}
              onClick={handleZoneClick}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  handleZoneClick();
                }
              }}
              onDragEnter={(e) => {
                e.preventDefault();
                setDragOver(true);
              }}
              onDragOver={(e) => {
                e.preventDefault();
                setDragOver(true);
              }}
              onDragLeave={(e) => {
                e.preventDefault();
                if (e.currentTarget === e.target) setDragOver(false);
              }}
              onDrop={(e) => void handleDrop(e)}
            >
              <div className="kb-dropzone-icon">
                <IconUpload />
              </div>
              <p className="kb-dropzone-title">
                {uploadMode === "folder"
                  ? "点击或拖拽文件夹至此区域即可上传"
                  : "点击或拖拽文件至此区域即可上传"}
              </p>
              <p className="kb-dropzone-hint">
                {uploadMode === "folder"
                  ? "支持选择或拖入整个文件夹；仅上传允许类型，单个文件 ≤ 50MB。禁止上传违规文件。"
                  : "支持单文件或多文件；类型 .txt / .md / .pdf / .docx / .pptx / .xlsx，单个 ≤ 50MB。禁止上传违规文件。"}
              </p>
            </div>

            {files.length > 0 ? (
              <ul className="doc-file-list kb-upload-file-list">
                {files.slice(0, 20).map((f) => (
                  <li key={`${f.webkitRelativePath || f.name}-${f.size}`}>
                    <span>
                      {uploadMode === "folder" && f.webkitRelativePath
                        ? f.webkitRelativePath
                        : fileBaseName(f.name)}
                    </span>
                    <span className="muted">{formatBytes(f.size)}</span>
                  </li>
                ))}
                {files.length > 20 ? (
                  <li className="muted">…还有 {files.length - 20} 个文件</li>
                ) : null}
              </ul>
            ) : null}
          </div>

          {showTitle ? (
            <label className="kb-modal-field">
              <span className="kb-modal-label">
                文档标题 <span className="kb-required">*</span>
              </span>
              <input
                type="text"
                value={title}
                maxLength={255}
                placeholder="选择文件后自动填入文件名，可修改"
                disabled={busy || files.length === 0}
                onChange={(e) => setTitle(e.target.value)}
              />
            </label>
          ) : null}

          <label className="kb-modal-field">
            <span className="kb-modal-label">
              文档分类 <span className="kb-required">*</span>
            </span>
            <select
              value={tag}
              disabled={busy}
              onChange={(e) => setTag(e.target.value as DocTag | "")}
            >
              <option value="">请选择…</option>
              {TAG_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label} — {opt.description}
                </option>
              ))}
            </select>
          </label>

          {localError ? (
            <p className="kb-modal-error" role="alert">
              {localError}
            </p>
          ) : null}

          {reviewFormOpen ? (
            <div className="kb-review-panel">
              <label className="kb-modal-field">
                <span className="kb-modal-label">
                  选择审核人 <span className="kb-required">*</span>
                </span>
                <select
                  value={reviewerUserId}
                  disabled={busy}
                  onChange={(e) => setReviewerUserId(e.target.value)}
                >
                  <option value="">请选择…</option>
                  {reviewers.map((r) => (
                    <option key={r.user_id} value={r.user_id}>
                      {r.name} ({r.email})
                    </option>
                  ))}
                </select>
              </label>
              <label className="kb-modal-field">
                <span className="kb-modal-label">备注信息（给审核人）</span>
                <textarea
                  value={reviewComment}
                  rows={3}
                  maxLength={1000}
                  placeholder="请输入提交给审核人的备注信息（可选）"
                  disabled={busy}
                  onChange={(e) => setReviewComment(e.target.value)}
                />
              </label>
            </div>
          ) : null}

          <div className="doc-actions kb-modal-doc-actions">
            <button
              type="button"
              className="btn"
              disabled={busy}
              onClick={() => void handleAction("draft")}
            >
              {busy ? "保存中…" : "保存草稿"}
            </button>
            <button
              type="button"
              className="btn primary"
              disabled={busy}
              onClick={() => void handleAction("review")}
            >
              {busy ? "提交中…" : reviewFormOpen ? "提交" : "提交审核"}
            </button>
          </div>

          <p className="doc-version-line">
            当前版本：{formatVersionDisplay(1)}
          </p>

          <IngestJobStatusCard job={null} published={false} />
        </div>
      </div>
    </div>
  );
}
