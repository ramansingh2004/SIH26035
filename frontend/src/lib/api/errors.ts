import type { ApiErrorBody } from "./types";

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: Record<string, unknown>;
  readonly requestId: string | null;

  constructor(
    status: number,
    code: string,
    message: string,
    details: Record<string, unknown> = {},
    requestId: string | null = null,
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
    this.requestId = requestId;
  }
}

export async function apiErrorFromResponse(
  response: Response,
): Promise<ApiError> {
  let body: ApiErrorBody = {};

  try {
    body = (await response.json()) as ApiErrorBody;
  } catch {
    // Preserve the HTTP status even when a proxy/network boundary did not
    // return the backend's normal JSON error envelope.
  }

  return new ApiError(
    response.status,
    body.error?.code ?? "HTTP_ERROR",
    body.error?.message ?? "The request could not be completed.",
    body.error?.details ?? {},
    body.error?.request_id ?? response.headers.get("X-Request-ID"),
  );
}

const FRIENDLY_MESSAGES: Record<string, string> = {
  AUTHENTICATION_REQUIRED: "Your session has expired. Sign in again.",
  INVALID_CREDENTIALS: "The email or password is incorrect.",
  PERMISSION_DENIED: "You do not have permission for this action.",
  RESOURCE_NOT_FOUND: "The requested record could not be found.",
  TODO_REGULATORY_VALIDATION:
    "Required regulatory rules have not yet been verified for authoritative use.",
  TEST_NOT_APPLICABLE: "This test is not applicable to the current evaluation.",
  TEST_ALREADY_LOCKED: "This test is locked and cannot be changed.",
  MISSING_REQUIRED_OBSERVATIONS:
    "Required observations are incomplete. Complete the test data before evaluation.",
  SESSION_NOT_READY_FOR_REVIEW:
    "This evaluation is not yet ready for technical review.",
  SESSION_NOT_READY_FOR_APPROVAL:
    "This evaluation is not yet ready for final approval.",
  CORRECTION_SCOPE_VIOLATION:
    "This field is outside the correction scope authorized by the reviewer.",
  SOURCE_CHANGED_DURING_EVALUATION:
    "Source data changed during evaluation. Reload and evaluate the current revision.",
  PRECONDITION_REQUIRED: "Reload this record before making changes.",
  VERSION_CONFLICT:
    "This record was changed by another user. Reload the current version before continuing.",
  IDEMPOTENCY_CONFLICT:
    "This action key was already used for a different request. Start the action again.",
  OPERATION_IN_PROGRESS: "This operation is already in progress.",
  REPORT_ALREADY_ISSUED: "This report has already been officially issued.",
  REPORT_GENERATION_FAILED:
    "Report generation failed. Review the generation details before retrying.",
  REPORT_CHAIN_CONFLICT:
    "The report revision chain changed. Reload the report before continuing.",
  ISSUE_METADATA_MISMATCH:
    "Issuer or planned issue metadata changed. Regenerate the unissued report first.",
  FILE_INVALID: "The selected file did not pass verification.",
  FILE_TOO_LARGE: "The selected file exceeds the permitted size.",
};

export function friendlyApiMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return FRIENDLY_MESSAGES[error.code] ?? error.message;
  }
  return "An unexpected error occurred. Please try again.";
}
