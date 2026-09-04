import React, { useState, useEffect } from "react";
import {
  FileText,
  Upload,
  AlertCircle,
  CheckCircle2,
  Loader2,
  ChevronDown,
  ChevronUp,
  Image as ImageIcon,
  ZoomIn,
  ZoomOut,
  RotateCcw,
  Eye,
  X,
} from "lucide-react";
import { toast } from "sonner";
import { apiRequest } from "@/lib/api";

interface DocumentContent {
  text: string;
  pages: number;
}

interface DocumentInfo {
  id: string;
  filename: string;
  fileType: string;
  size: number;
  status: string;
}

interface DocumentUploadResponse {
  success: boolean;
  document?: DocumentInfo;
  content?: DocumentContent;
  error?: {
    code: string;
    message: string;
  };
}

export function DocumentUploadCard() {
  const [dragActive, setDragActive] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [status, setStatus] = useState<"idle" | "uploading" | "processed" | "error">("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [extractedData, setExtractedData] = useState<{
    document: DocumentInfo;
    content: DocumentContent;
  } | null>(null);
  const [showTextPreview, setShowTextPreview] = useState(false);
  const [showImageModal, setShowImageModal] = useState(false);
  const [zoomLevel, setZoomLevel] = useState(1);

  useEffect(() => {
    return () => {
      if (previewUrl) {
        URL.revokeObjectURL(previewUrl);
      }
    };
  }, [previewUrl]);

  function isImageFile(f: File | string): boolean {
    const name = typeof f === "string" ? f : f.name;
    const ext = "." + name.split(".").pop()?.toLowerCase();
    return [".png", ".jpg", ".jpeg", ".webp"].includes(ext);
  }

  function validateFile(selectedFile: File): string | null {
    const allowedExts = [".pdf", ".docx", ".doc", ".png", ".jpg", ".jpeg", ".webp"];
    const ext = "." + selectedFile.name.split(".").pop()?.toLowerCase();

    if (!allowedExts.includes(ext)) {
      return `Invalid format '${ext}'. Supported: PDF, DOCX, PNG, JPG, JPEG, WEBP.`;
    }

    const MAX_SIZE_MB = 25;
    if (selectedFile.size > MAX_SIZE_MB * 1024 * 1024) {
      return `File size exceeds the ${MAX_SIZE_MB}MB maximum limit.`;
    }

    if (selectedFile.size === 0) {
      return "Selected file is empty (0 bytes).";
    }

    return null;
  }

  async function processFile(selectedFile: File) {
    const error = validateFile(selectedFile);
    if (error) {
      setErrorMessage(error);
      setStatus("error");
      toast.error(error);
      return;
    }

    if (previewUrl) {
      URL.revokeObjectURL(previewUrl);
    }

    setFile(selectedFile);
    if (isImageFile(selectedFile)) {
      const url = URL.createObjectURL(selectedFile);
      setPreviewUrl(url);
    } else {
      setPreviewUrl(null);
    }

    setStatus("uploading");
    setErrorMessage(null);
    setExtractedData(null);
    setZoomLevel(1);

    const formData = new FormData();
    formData.append("file", selectedFile);

    try {
      const res = await apiRequest<DocumentUploadResponse>("/v1/uploads/documents", {
        method: "POST",
        body: formData,
      });

      if (res.success && res.document && res.content) {
        setExtractedData({ document: res.document, content: res.content });
        setStatus("processed");
        toast.success(`Extracted document data from ${res.document.filename}`);
      } else {
        const msg = res.error?.message || "Document extraction failed.";
        setErrorMessage(msg);
        setStatus("error");
        toast.error(msg);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Document upload failed.";
      setErrorMessage(msg);
      setStatus("error");
      toast.error(msg);
    }
  }

  function handleDrag(e: React.DragEvent) {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      void processFile(e.dataTransfer.files[0]);
    }
  }

  function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    e.preventDefault();
    if (e.target.files && e.target.files[0]) {
      void processFile(e.target.files[0]);
    }
  }

  return (
    <div className="panel p-4 bg-[var(--lc-surface)] border border-[var(--lc-border)] rounded-[6px] shadow-sm">
      <div className="flex items-center justify-between gap-2 border-b border-[var(--lc-border)] pb-3">
        <div className="flex items-center gap-2">
          <div className="flex size-7 items-center justify-center rounded-[4px] bg-[var(--lc-accent-soft)] border border-[rgba(168,85,247,0.25)] text-[var(--lc-accent)]">
            <FileText className="size-4" />
          </div>
          <div>
            <h3 className="font-display text-xs font-semibold text-[var(--lc-text-primary)]">
              Document & Receipt Ingestion Engine
            </h3>
            <p className="text-[11px] text-[var(--lc-text-muted)]">
              Upload PDF statements, Word summaries, or receipt images (PNG, JPG, WEBP)
            </p>
          </div>
        </div>
        <span className="font-mono text-[10px] font-bold text-[var(--lc-accent)] bg-[var(--lc-accent-soft)] border border-[rgba(168,85,247,0.25)] px-2 py-0.5 rounded-[3px] uppercase">
          AI OCR Pipeline
        </span>
      </div>

      <div className="mt-4">
        <div
          onDragEnter={handleDrag}
          onDragLeave={handleDrag}
          onDragOver={handleDrag}
          onDrop={handleDrop}
          className={`relative flex flex-col items-center justify-center rounded-[6px] border border-dashed p-5 text-center transition-all ${
            dragActive
              ? "border-[var(--lc-accent)] bg-[var(--lc-accent-soft)]"
              : "border-[var(--lc-border)] bg-[var(--lc-surface-secondary)] hover:border-[var(--lc-accent)]"
          }`}
        >
          <input
            type="file"
            id="doc-file-upload"
            className="hidden"
            accept=".pdf,.docx,.doc,.png,.jpg,.jpeg,.webp"
            onChange={handleChange}
            disabled={status === "uploading"}
          />

          {status === "uploading" ? (
            <div className="flex flex-col items-center py-2">
              <Loader2 className="size-6 animate-spin text-[var(--lc-accent)]" />
              <p className="mt-2 font-mono text-xs font-medium text-[var(--lc-text-primary)]">
                Extracting structured data from asset...
              </p>
              <p className="text-[11px] text-[var(--lc-text-muted)]">
                Parsing tabular records and financial entities
              </p>
            </div>
          ) : (
            <div className="flex flex-col items-center">
              <div className="flex size-9 items-center justify-center rounded-[6px] bg-[var(--lc-surface-elevated)] border border-[var(--lc-border)] text-[var(--lc-text-muted)] mb-2">
                <Upload className="size-4" />
              </div>
              <p className="text-xs font-medium text-[var(--lc-text-primary)]">
                Drag and drop your statement or receipt image here, or{" "}
                <label
                  htmlFor="doc-file-upload"
                  className="cursor-pointer font-semibold text-[var(--lc-accent)] hover:underline"
                >
                  browse computer
                </label>
              </p>
              <p className="mt-1 text-[10px] font-mono text-[var(--lc-text-muted)]">
                Supported: .pdf, .docx, .png, .jpg, .webp (up to 25MB)
              </p>
            </div>
          )}
        </div>

        {errorMessage && (
          <div className="mt-3 flex items-center gap-2 rounded-[6px] border border-[rgba(239,68,68,0.3)] bg-[rgba(239,68,68,0.08)] p-2.5 text-xs text-[var(--lc-danger)]">
            <AlertCircle className="size-4 shrink-0" />
            <span>{errorMessage}</span>
          </div>
        )}

        {status === "processed" && extractedData && (
          <div className="mt-3 rounded-[6px] border border-[rgba(34,197,94,0.3)] bg-[rgba(34,197,94,0.06)] p-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <CheckCircle2 className="size-4 text-[var(--lc-success)]" />
                <div>
                  <span className="font-mono text-xs font-bold text-[var(--lc-text-primary)]">
                    {extractedData.document.filename}
                  </span>
                  <span className="ml-2 font-mono text-[11px] text-[var(--lc-success)]">
                    {extractedData.content.pages} Page(s) Extracted ·{" "}
                    {(extractedData.document.size / 1024).toFixed(1)} KB
                  </span>
                </div>
              </div>
              <div className="flex items-center gap-2">
                {previewUrl && (
                  <button
                    type="button"
                    onClick={() => setShowImageModal(true)}
                    className="lc-btn lc-btn--primary text-[11px] py-1 px-2.5 flex items-center gap-1.5"
                  >
                    <Eye className="size-3.5" /> Inspect Image
                  </button>
                )}
                <button
                  type="button"
                  onClick={() => setShowTextPreview((prev) => !prev)}
                  className="lc-btn lc-btn--ghost text-[11px] py-1 px-2 flex items-center gap-1"
                >
                  {showTextPreview ? (
                    <>
                      <ChevronUp className="size-3" /> Hide Text
                    </>
                  ) : (
                    <>
                      <ChevronDown className="size-3" /> Inspect Text
                    </>
                  )}
                </button>
              </div>
            </div>

            {showTextPreview && (
              <div className="mt-2 rounded-[6px] border border-[var(--lc-border)] bg-[var(--lc-bg)] p-3 font-mono text-[11px] text-[var(--lc-text-secondary)]">
                <div className="flex items-center justify-between border-b border-[var(--lc-border)] pb-1 mb-2 text-[10px] text-[var(--lc-text-muted)] uppercase">
                  <span>Extracted Raw Text Preview</span>
                  <span>{extractedData.content.text.length} characters</span>
                </div>
                <div className="max-h-40 overflow-y-auto whitespace-pre-wrap leading-relaxed">
                  {extractedData.content.text || "No text content found in document."}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Image Inspection Modal */}
      {showImageModal && previewUrl && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 animate-in fade-in duration-150">
          <div className="relative flex flex-col w-full max-w-4xl max-h-[90vh] bg-[var(--lc-surface)] border border-[var(--lc-border)] rounded-[8px] shadow-2xl overflow-hidden">
            <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--lc-border)] bg-[var(--lc-surface-elevated)]">
              <div className="flex items-center gap-2">
                <ImageIcon className="size-4 text-[var(--lc-accent)]" />
                <span className="text-xs font-semibold text-[var(--lc-text-primary)] font-mono">
                  {file?.name || "Image Inspection"}
                </span>
                <span className="text-[10px] text-[var(--lc-text-muted)] font-mono">
                  Zoom: {Math.round(zoomLevel * 100)}%
                </span>
              </div>
              <div className="flex items-center gap-1.5">
                <button
                  type="button"
                  onClick={() => setZoomLevel((z) => Math.min(3, z + 0.25))}
                  className="lc-btn lc-btn--secondary p-1.5"
                  title="Zoom In"
                >
                  <ZoomIn className="size-3.5" />
                </button>
                <button
                  type="button"
                  onClick={() => setZoomLevel((z) => Math.max(0.5, z - 0.25))}
                  className="lc-btn lc-btn--secondary p-1.5"
                  title="Zoom Out"
                >
                  <ZoomOut className="size-3.5" />
                </button>
                <button
                  type="button"
                  onClick={() => setZoomLevel(1)}
                  className="lc-btn lc-btn--secondary p-1.5"
                  title="Reset Zoom"
                >
                  <RotateCcw className="size-3.5" />
                </button>
                <button
                  type="button"
                  onClick={() => setShowImageModal(false)}
                  className="lc-btn lc-btn--ghost p-1.5 text-[var(--lc-text-muted)] hover:text-[var(--lc-text-primary)] ml-2"
                >
                  <X className="size-4" />
                </button>
              </div>
            </div>

            <div className="flex-1 overflow-auto p-6 flex items-center justify-center bg-[var(--lc-bg)] min-h-[350px]">
              <div
                style={{ transform: `scale(${zoomLevel})`, transition: "transform 150ms ease" }}
                className="max-w-full flex items-center justify-center origin-center"
              >
                <img
                  src={previewUrl}
                  alt={file?.name || "Uploaded document preview"}
                  className="max-h-[65vh] max-w-full rounded-[4px] object-contain border border-[var(--lc-border)] shadow-md"
                />
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
