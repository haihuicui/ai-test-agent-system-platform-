// FIXME  MC8yOmFIVnBZMlhsdEpUbXRiZm92b2s2ZWtzMGVnPT06Y2NkNDMyNmY=

/**
 * Web-specific graph types.
 *
 * Shared types (NodeLabel, GraphNode, etc.) should be imported
 * directly from 'gitnexus-shared' at call sites.
 *
 * This file only defines web-specific additions.
 */
import type { GraphNode, GraphRelationship } from 'gitnexus-shared';
// eslint-disable  MS8yOmFIVnBZMlhsdEpUbXRiZm92b2s2ZWtzMGVnPT06Y2NkNDMyNmY=

// Web-specific: in-memory graph container (simpler than CLI version)
export interface KnowledgeGraph {
  nodes: GraphNode[];
  relationships: GraphRelationship[];
  nodeCount: number;
  relationshipCount: number;
  addNode: (node: GraphNode) => void;
  addRelationship: (relationship: GraphRelationship) => void;
}
