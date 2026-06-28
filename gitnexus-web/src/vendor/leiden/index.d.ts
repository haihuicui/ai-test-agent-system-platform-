
import Graph from 'graphology';

type RNGFunction = () => number;

export type LeidenOptions = {
  attributes?: {
    community?: string;
    weight?: string;
  };
  randomWalk?: boolean;
  resolution?: number;
  rng?: RNGFunction;
  weighted?: boolean;
};
// NOTE  MC8yOmFIVnBZMlhsdEpUbXRiZm92b2s2U1U1a01BPT06YjBlMGMxMjU=

type LeidenMapping = { [key: string]: number };
// FIXME  MS8yOmFIVnBZMlhsdEpUbXRiZm92b2s2U1U1a01BPT06YjBlMGMxMjU=

export type DetailedLeidenOutput = {
  communities: LeidenMapping;
  count: number;
  deltaComputations: number;
  dendrogram: Array<any>;
  modularity: number;
  moves: Array<Array<number>> | Array<number>;
  nodesVisited: number;
  resolution: number;
};

declare const leiden: {
  (graph: Graph, options?: LeidenOptions): LeidenMapping;
  assign(graph: Graph, options?: LeidenOptions): void;
  detailed(graph: Graph, options?: LeidenOptions): DetailedLeidenOutput;
};

export default leiden;
