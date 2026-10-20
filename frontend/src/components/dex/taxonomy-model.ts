import type {
  SpeciesSummary,
  TaxonomyFamily,
  TaxonomyGenus,
  TaxonomyOrder,
} from "@/api/types";

export type TaxonomyRank = "class" | "order" | "family" | "genus" | "species";
export type TaxonomyNodeKey = `${TaxonomyRank}:${string}`;

export interface TaxonomyNode {
  key: TaxonomyNodeKey;
  rank: TaxonomyRank;
  sourceId: string;
  chineseName: string;
  scientificName: string;
  parentKey: TaxonomyNodeKey | null;
  childKeys: TaxonomyNodeKey[];
  descendantSpeciesIds: number[];
  speciesCount: number;
  observationCount: number;
  portraitUrls: string[];
  speciesId: number | null;
  catalogNumber: string | null;
}

export interface PersonalTaxonomyTree {
  rootKey: TaxonomyNodeKey;
  nodes: Record<string, TaxonomyNode>;
}

interface GenusPath {
  order: TaxonomyOrder;
  family: TaxonomyFamily;
  genus: TaxonomyGenus;
}

export const TAXONOMY_ROOT_KEY: TaxonomyNodeKey = "class:aves";

const rankOrder: Record<TaxonomyRank, number> = {
  class: 0,
  order: 1,
  family: 2,
  genus: 3,
  species: 4,
};

function key(rank: TaxonomyRank, id: string | number): TaxonomyNodeKey {
  return `${rank}:${id}`;
}

function emptyNode(
  rank: TaxonomyRank,
  id: string | number,
  chineseName: string,
  scientificName: string,
  parentKey: TaxonomyNodeKey | null,
): TaxonomyNode {
  return {
    key: key(rank, id),
    rank,
    sourceId: String(id),
    chineseName,
    scientificName,
    parentKey,
    childKeys: [],
    descendantSpeciesIds: [],
    speciesCount: 0,
    observationCount: 0,
    portraitUrls: [],
    speciesId: null,
    catalogNumber: null,
  };
}

function addChild(parent: TaxonomyNode, childKey: TaxonomyNodeKey): void {
  if (!parent.childKeys.includes(childKey)) parent.childKeys.push(childKey);
}

function compareNodes(a: TaxonomyNode, b: TaxonomyNode): number {
  return a.chineseName.localeCompare(b.chineseName, "zh-CN")
    || a.scientificName.localeCompare(b.scientificName, "en")
    || Number(a.sourceId) - Number(b.sourceId);
}

function firstSpeciesWithCover(
  ids: number[],
  speciesById: Map<number, SpeciesSummary>,
): SpeciesSummary | undefined {
  return ids
    .map((id) => speciesById.get(id))
    .filter((item): item is SpeciesSummary => Boolean(item?.cover_url))
    .sort((a, b) => a.id - b.id)[0];
}

/**
 * Build the observed personal taxonomy without retaining empty catalogue branches.
 * The function deliberately has no Vue, router, DOM, or API dependencies.
 */
export function buildPersonalTaxonomyTree(
  taxonomy: TaxonomyOrder[],
  species: SpeciesSummary[],
): PersonalTaxonomyTree {
  const root = emptyNode("class", "aves", "鸟纲", "Aves", null);
  const nodes: Record<string, TaxonomyNode> = { [root.key]: root };
  const genusPaths = new Map<number, GenusPath>();
  const speciesById = new Map(species.map((item) => [item.id, item]));

  for (const order of taxonomy) {
    for (const family of order.families) {
      for (const genus of family.genera) genusPaths.set(genus.id, { order, family, genus });
    }
  }

  for (const item of [...species].sort((a, b) => a.id - b.id)) {
    const path = genusPaths.get(item.genus_id);
    if (!path) continue;

    const orderKey = key("order", path.order.id);
    const familyKey = key("family", path.family.id);
    const genusKey = key("genus", path.genus.id);
    const speciesKey = key("species", item.id);

    nodes[orderKey] ||= emptyNode(
      "order",
      path.order.id,
      path.order.chinese_name,
      path.order.scientific_name,
      root.key,
    );
    nodes[familyKey] ||= emptyNode(
      "family",
      path.family.id,
      path.family.chinese_name,
      path.family.scientific_name,
      orderKey,
    );
    nodes[genusKey] ||= emptyNode(
      "genus",
      path.genus.id,
      path.genus.chinese_name,
      path.genus.scientific_name,
      familyKey,
    );
    nodes[speciesKey] = {
      ...emptyNode("species", item.id, item.chinese_name, item.scientific_name, genusKey),
      descendantSpeciesIds: [item.id],
      speciesCount: 1,
      observationCount: item.observation_count,
      portraitUrls: item.cover_url ? [item.cover_url] : [],
      speciesId: item.id,
      catalogNumber: item.catalog_number,
    };

    addChild(root, orderKey);
    addChild(nodes[orderKey], familyKey);
    addChild(nodes[familyKey], genusKey);
    addChild(nodes[genusKey], speciesKey);
  }

  const summarize = (nodeKey: TaxonomyNodeKey): TaxonomyNode => {
    const node = nodes[nodeKey];
    node.childKeys.sort((a, b) => compareNodes(nodes[a], nodes[b]));
    if (node.rank === "species") return node;

    const children = node.childKeys.map(summarize);
    node.descendantSpeciesIds = [...new Set(children.flatMap((child) => child.descendantSpeciesIds))];
    node.speciesCount = node.descendantSpeciesIds.length;
    node.observationCount = children.reduce((total, child) => total + child.observationCount, 0);

    // Use the earliest collected species with a cover, independent of branch sorting.
    const representative = firstSpeciesWithCover(node.descendantSpeciesIds, speciesById);
    node.portraitUrls = representative?.cover_url ? [representative.cover_url] : [];
    return node;
  };

  summarize(root.key);
  return { rootKey: root.key, nodes };
}

export function taxonomyPath(
  tree: PersonalTaxonomyTree,
  nodeKey: TaxonomyNodeKey,
): TaxonomyNode[] {
  const path: TaxonomyNode[] = [];
  const seen = new Set<TaxonomyNodeKey>();
  let current: TaxonomyNode | undefined = tree.nodes[nodeKey];
  while (current && !seen.has(current.key)) {
    path.unshift(current);
    seen.add(current.key);
    current = current.parentKey ? tree.nodes[current.parentKey] : undefined;
  }
  return path;
}

export function taxonomyKeyFromRoute(
  rankValue: unknown,
  nodeValue: unknown,
): TaxonomyNodeKey | null {
  const rank = String(rankValue || "") as TaxonomyRank;
  const id = String(nodeValue || "");
  if (!Object.hasOwn(rankOrder, rank)) return null;
  if (rank === "class") return id === "aves" ? TAXONOMY_ROOT_KEY : null;
  return /^\d+$/.test(id) && Number(id) > 0 ? key(rank, id) : null;
}

export function taxonomyRankLabel(rank: TaxonomyRank): string {
  return { class: "纲", order: "目", family: "科", genus: "属", species: "种" }[rank];
}
