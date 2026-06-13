"use client";

import { useEffect } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

type Props = {
  documentId: string | null;
  documentName?: string | null;
  documentType?: string | null;
  onClose: () => void;
};

export default function ImageViewer({ documentId, documentName, documentType, onClose }: Props) {
  useEffect(() => {
    if (!documentId) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [documentId, onClose]);

  if (!documentId) return null;

  const fileUrl = `${API_URL}/documents/${documentId}/file`;
  const isImage =
    documentName && /\.(png|jpe?g|gif|webp|bmp)$/i.test(documentName);

  return (
    <div
      className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
    >
      <div
        className="bg-white rounded-xl shadow-xl max-w-4xl w-full max-h-[90vh] flex flex-col overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="px-5 py-3 border-b border-slate-200 flex items-center justify-between gap-4">
          <div className="min-w-0">
            <div className="font-medium text-slate-900 truncate">
              {documentName || documentId}
            </div>
            {documentType && (
              <div className="text-xs text-slate-500 mt-0.5">{documentType}</div>
            )}
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <a
              href={fileUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs text-blue-600 hover:underline"
            >
              Open in new tab
            </a>
            <button
              onClick={onClose}
              className="w-8 h-8 rounded-full hover:bg-slate-100 text-slate-500 hover:text-slate-900 flex items-center justify-center text-lg"
              aria-label="Close"
            >
              {"\u00d7"}
            </button>
          </div>
        </header>

        <div className="flex-1 min-h-0 bg-slate-100">
          {isImage ? (
            <img
              src={fileUrl}
              alt={documentName || documentId}
              className="w-full h-full object-contain"
            />
          ) : (
            <iframe
              src={fileUrl}
              title={documentName || documentId}
              className="w-full h-full border-0"
            />
          )}
        </div>
      </div>
    </div>
  );
}
