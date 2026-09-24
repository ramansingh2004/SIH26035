import { apiRequest } from "@/lib/api/client";
import { createIdempotencyKey } from "@/lib/api/idempotency";

import type {
  AttachmentDownload,
  CompletedAttachment,
  EvidenceMimeType,
  EvidenceTargetType,
  PresignResponse,
} from "./types";

const MAX_FILE_SIZE = 25 * 1024 * 1024;
const ALLOWED_TYPES = new Set<EvidenceMimeType>([
  "application/pdf",
  "image/png",
  "image/jpeg",
]);

export async function sha256File(file: File): Promise<string> {
  const bytes = await file.arrayBuffer();
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(digest))
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
}

export function validateEvidenceFile(file: File): EvidenceMimeType {
  if (!ALLOWED_TYPES.has(file.type as EvidenceMimeType)) {
    throw new Error("Evidence must be a PDF, PNG, or JPEG file.");
  }
  if (file.size <= 0 || file.size > MAX_FILE_SIZE) {
    throw new Error(
      "Evidence must be larger than 0 bytes and no more than 25 MiB.",
    );
  }
  return file.type as EvidenceMimeType;
}

export async function uploadEvidence(input: {
  file: File;
  laboratoryId: string;
  entityType: EvidenceTargetType;
  entityId: string;
  purpose: string;
  targetEtag: string;
}): Promise<CompletedAttachment> {
  const contentType = validateEvidenceFile(input.file);
  const sha256 = await sha256File(input.file);

  const presign = await apiRequest<PresignResponse>(
    "/api/v1/attachments/presign",
    {
      method: "POST",
      etag: input.targetEtag,
      idempotencyKey: createIdempotencyKey(),
      body: {
        laboratory_id: input.laboratoryId,
        entity_type: input.entityType,
        entity_id: input.entityId,
        purpose: input.purpose,
        file_name: input.file.name,
        content_type: contentType,
        file_size: input.file.size,
        sha256,
      },
    },
  );

  const uploadHeaders = new Headers();
  for (const [name, value] of Object.entries(presign.data.headers)) {
    if (name.toLowerCase() !== "content-length") {
      uploadHeaders.set(name, value);
    }
  }

  const uploadResponse = await fetch(presign.data.upload_url, {
    method: presign.data.method,
    headers: uploadHeaders,
    body: input.file,
  });

  if (!uploadResponse.ok) {
    throw new Error(
      `Private object upload failed with status ${uploadResponse.status}.`,
    );
  }

  const completed = await apiRequest<CompletedAttachment>(
    "/api/v1/attachments/complete",
    {
      method: "POST",
      etag: input.targetEtag,
      idempotencyKey: createIdempotencyKey(),
      body: { upload_id: presign.data.upload_id },
    },
  );

  return completed.data;
}

export async function downloadEvidence(
  attachmentId: string,
): Promise<AttachmentDownload> {
  return (
    await apiRequest<AttachmentDownload>(
      `/api/v1/attachments/${attachmentId}/download`,
    )
  ).data;
}
