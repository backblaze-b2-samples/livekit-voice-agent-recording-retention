// GENERATED FILE — DO NOT EDIT.
//
// Written by `pnpm gen:api` from:
//   docs/api/openapi.json
//
// Hand edits are discarded by the next `pnpm gen:api`. `pnpm gen:check`
// (part of `pnpm verify:web`) fails while this file disagrees with the
// contract. To change what is here, change the FastAPI route or Pydantic
// model and re-run `pnpm contract:export && pnpm gen:api`.

/** Dashboard figures, computed from the session manifests in B2. */
export interface ArchiveStats {
  by_class: CountBucket[];
  by_status: CountBucket[];
  last_report: RetentionReportSummary | null;
  passed_evaluations: number;
  recent_sessions: SessionSummary[];
  recorded_bytes: number;
  recorded_bytes_human: string;
  recorded_seconds: number;
  total_sessions: number;
}

export interface ClassPolicy {
  /** Null means keep indefinitely. */
  retain_days: number | null;
  session_class: string;
}

export interface CountBucket {
  count: number;
  name: string;
}

/** Acknowledgement that one object was removed from the bucket. */
export interface DeleteFileResponse {
  deleted: boolean;
  key: string;
}

export interface EgressState {
  egress_id: string | null;
  ended_at: string | null;
  error: string | null;
  started_at: string | null;
  /** LiveKit EgressStatus name. */
  status: string | null;
  webhook: WebhookRef | null;
}

/**
 * `evaluation.json`: deterministic score of the transcript against the
 * script.
 */
export interface Evaluation {
  expected_phrases: string[];
  hypothesis_text: string;
  max_wer: number;
  passed: boolean;
  phrases_found: string[];
  phrases_missing: string[];
  reference_text: string;
  script_id: string;
  session_id: string;
  wer: number;
}

export interface EvaluationInfo {
  expected_phrases_found: number;
  expected_phrases_total: number;
  key: string;
  passed: boolean;
  wer: number;
}

/** One stored object as the file list and the by-key metadata route see it. */
export interface FileMetadata {
  content_type: string;
  filename: string;
  folder: string;
  key: string;
  size_bytes: number;
  size_human: string;
  uploaded_at: string;
  /**
   * Public object URL, set only when B2_PUBLIC_URL_BASE is configured and
   * the bucket is public. Null otherwise — the UI asks for a presigned URL
   * instead.
   */
  url: string | null;
}

/** Rich metadata recomputed on demand by re-reading the stored object. */
export interface FileMetadataDetail {
  /** Audio/video: bits per second. */
  bitrate: number | null;
  /** Audio/video: codec name. */
  codec: string | null;
  /** Audio/video: duration in seconds. */
  duration_seconds: number | null;
  /**
   * Image-specific: EXIF tags, values stringified. Null for non-images or
   * when no EXIF block was present.
   */
  exif: Record<string, string> | null;
  extension: string;
  filename: string;
  /** Image-specific: pixel height. Null for non-images. */
  image_height: number | null;
  /** Image-specific: pixel width. Null for non-images. */
  image_width: number | null;
  md5: string;
  /**
   * Set when a format-specific extractor was skipped or failed (e.g. an
   * image above Pillow's decompression-bomb limit). The core fields are
   * always exact, so the UI shows this instead of silently dropping the
   * Image / PDF section.
   */
  metadata_warning: string | null;
  mime_type: string;
  /** PDF-specific: author. */
  pdf_author: string | null;
  /** PDF-specific: page count. Null for non-PDFs. */
  pdf_pages: number | null;
  /** PDF-specific: title. */
  pdf_title: string | null;
  sha256: string;
  size_bytes: number;
  size_human: string;
  uploaded_at: string;
}

/** A short-lived presigned GET for downloading or previewing one object. */
export interface FileUrlResponse {
  /**
   * Presigned GET URL. Download URLs force an attachment disposition;
   * preview URLs are signed inline so a PDF renders in place.
   */
  url: string;
}

export interface HTTPValidationError {
  detail?: ValidationError[];
}

/**
 * Liveness plus B2 and LiveKit reachability. The route answers HTTP 200
 * even when a dependency is unreachable, so a caller must read the flags
 * rather than trusting the status code.
 */
export interface HealthStatus {
  /** True when the bucket answered a cheap head request. */
  b2_connected: boolean;
  /** True when the LiveKit server answered a room list request. */
  livekit_connected: boolean;
  /** "healthy" when B2 answered, else "degraded". */
  status: string;
}

export interface JoinToken {
  room: string;
  token: string;
  url: string;
}

export interface JoinTokenRequest {
  identity: string;
}

export interface RecordingInfo {
  content_type: string;
  duration_s: number | null;
  etag: string | null;
  filename: string | null;
  /** Deterministic key Egress was told to write. */
  key: string;
  /** file_results[0].location from Egress. */
  location: string | null;
  sha256: string | null;
  size_bytes: number | null;
}

export interface RetentionClassResult {
  already_expired: string[];
  kept: string[];
  removed: string[];
  retain_days: number | null;
  session_class: string;
}

export interface RetentionInfo {
  removed_at: string | null;
  /** Null means keep indefinitely (hold). */
  retain_days: number | null;
  retain_until: string | null;
  session_class: string;
}

export interface RetentionPolicy {
  classes: ClassPolicy[];
}

/**
 * `reports/<as_of>.json`, written by an applied (non dry-run) retention
 * run.
 */
export interface RetentionReport {
  as_of: string;
  classes: RetentionClassResult[];
  date: string;
  dry_run: boolean;
  generated_at: string;
  kept_total: number;
  removed_bytes: number;
  removed_total: number;
  /** Where the report was written; null for a dry run. */
  report_key: string | null;
  schema_version: number;
}

export interface RetentionReportList {
  items: RetentionReportSummary[];
}

export interface RetentionReportSummary {
  date: string;
  generated_at: string | null;
  kept_total: number;
  key: string;
  removed_total: number;
}

export interface RetentionRunRequest {
  /** Defaults to today (UTC). */
  as_of?: string | null;
  dry_run?: boolean;
}

export interface ScriptInfo {
  description: string;
  expected_duration_s: number;
  id: string;
  line_count: number;
  title: string;
}

export interface ScriptList {
  items: ScriptInfo[];
}

export interface SessionCreate {
  label?: string;
  mode?: string;
  script_id: string;
  session_class?: string;
}

export interface SessionDetail {
  evaluation: Evaluation | null;
  manifest: SessionManifest;
  /** Presigned GET for playback, when the recording exists. */
  recording_url: string | null;
  transcript: Transcript | null;
  webhooks: WebhookEvidence[];
}

export interface SessionList {
  items: SessionSummary[];
  next_cursor: string | null;
}

/** `sessions/<date>/<room>/manifest.json` in B2. */
export interface SessionManifest {
  created_at: string;
  date: string;
  egress: EgressState;
  error: string | null;
  evaluation: EvaluationInfo | null;
  label: string;
  mode: string;
  recording: RecordingInfo;
  retention: RetentionInfo;
  schema_version: number;
  script_id: string;
  session_class: string;
  session_id: string;
  status: string;
  transcription: TranscriptionInfo | null;
}

export interface SessionSummary {
  created_at: string;
  date: string;
  duration_s: number | null;
  label: string;
  mode: string;
  passed: boolean | null;
  retain_until: string | null;
  script_id: string;
  session_class: string;
  session_id: string;
  size_bytes: number | null;
  status: string;
  wer: number | null;
}

export interface SessionUpdate {
  label?: string | null;
  session_class?: string | null;
}

/** `transcript.json`: what faster-whisper heard in the recording. */
export interface Transcript {
  device: string;
  language: string | null;
  model: string;
  segments: TranscriptSegment[];
  session_id: string;
  text: string;
}

export interface TranscriptSegment {
  end: number;
  start: number;
  text: string;
}

export interface TranscriptionInfo {
  device: string;
  key: string;
  language: string | null;
  model: string;
  word_count: number;
}

export interface ValidationError {
  ctx?: Record<string, unknown>;
  input?: unknown;
  loc: (string | number)[];
  msg: string;
  type: string;
}

export interface WebhookAck {
  duplicate: boolean;
  event: string;
  received: boolean;
}

export interface WebhookEvidence {
  event: string;
  event_id: string;
  key: string;
}

/** The verified webhook that last changed this session's Egress state. */
export interface WebhookRef {
  event: string;
  event_id: string;
  /** B2 key of the raw, verified webhook body. */
  evidence_key: string;
  received_at: string;
}
