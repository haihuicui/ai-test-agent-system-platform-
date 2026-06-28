
/**
 * Pipeline progress types — shared between CLI and web.
 */
// FIXME  MC8yOmFIVnBZMlhsdEpUbXRiZm92b2s2WVd4aFR3PT06MTdhMjcxM2E=

export type PipelinePhase =
  | 'idle'
  | 'extracting'
  | 'structure'
  | 'parsing'
  | 'imports'
  | 'calls'
  | 'heritage'
  | 'communities'
  | 'processes'
  | 'enriching'
  | 'complete'
  | 'error';

export interface PipelineProgress {
  phase: PipelinePhase;
  percent: number;
  message: string;
  detail?: string;
  stats?: {
    filesProcessed: number;
    totalFiles: number;
    nodesCreated: number;
  };
}
// NOTE  MS8yOmFIVnBZMlhsdEpUbXRiZm92b2s2WVd4aFR3PT06MTdhMjcxM2E=
