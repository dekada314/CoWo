from itertools import combinations

from falkordb.asyncio import FalkorDB

from src.application.interfaces.storages.graph_storage import (
    GraphCommunity,
    GraphProjection,
    GraphStorage,
)
from src.domain.exceptions import GraphStorageError


class FalkorDBStorage(GraphStorage):
    def __init__(self, client: FalkorDB, graph_name: str):
        self._client = client
        self._graph_name = graph_name

    def _graph(self):
        return self._client.select_graph(self._graph_name)

    @staticmethod
    def _already_exists(exc: Exception) -> bool:
        message = str(exc).casefold()
        return "already" in message or "exists" in message

    async def _create_index(self, query: str) -> None:
        try:
            await self._graph().query(query)
        except Exception as exc:
            if not self._already_exists(exc):
                raise

    async def _create_constraint(self, label: str, property_name: str) -> None:
        try:
            await self._client.execute_command(
                "GRAPH.CONSTRAINT",
                "CREATE",
                self._graph_name,
                "UNIQUE",
                "NODE",
                label,
                "PROPERTIES",
                1,
                property_name,
            )
        except Exception as exc:
            if not self._already_exists(exc):
                raise

    async def _validate_vector_indexes(self, dimension: int) -> None:
        result = await self._graph().query("CALL db.indexes()")
        expected = {"Domain", "Concept"}
        found: set[str] = set()
        for row in result.result_set:
            label, properties, types, options = row[:4]
            if (
                label not in expected
                or "embedding" not in properties
                or "VECTOR" not in str(types.get("embedding", []))
            ):
                continue
            vector_options = options.get("embedding", {})
            actual_dimension = int(vector_options.get("dimension", -1))
            similarity = str(vector_options.get("similarityFunction", "")).casefold()
            if actual_dimension != dimension or similarity != "cosine":
                raise ValueError(
                    f"invalid {label}.embedding vector index: "
                    f"dimension={actual_dimension}, similarity={similarity}"
                )
            found.add(label)
        missing = expected - found
        if missing:
            raise ValueError(f"missing vector indexes: {', '.join(sorted(missing))}")

    async def ensure_schema(self, dimension: int) -> None:
        try:
            for label in ("Community", "Domain", "Concept"):
                await self._create_index(f"CREATE INDEX FOR (n:{label}) ON (n.id)")
                await self._create_constraint(label, "id")
            for label in ("Domain", "Concept"):
                await self._create_index(
                    f"CREATE VECTOR INDEX FOR (n:{label}) ON (n.embedding) "
                    f"OPTIONS {{dimension: {dimension}, similarityFunction: 'cosine'}}"
                )
            await self._validate_vector_indexes(dimension)
            await self._graph().query(
                """
                MATCH (card:Card)-[:MENTIONS]->(concept:Concept)
                WITH concept, collect(DISTINCT card.id) AS legacy_card_ids
                SET concept.card_ids = CASE
                    WHEN concept.card_ids IS NULL THEN legacy_card_ids
                    ELSE concept.card_ids + [
                        card_id IN legacy_card_ids
                        WHERE NOT card_id IN concept.card_ids
                    ]
                END
                """
            )
            await self._graph().query("MATCH (card:Card) DETACH DELETE card")
        except Exception as exc:
            raise GraphStorageError(f"ensure_schema failed: {exc}") from exc

    async def project(self, projection: GraphProjection) -> None:
        graph = self._graph()
        try:
            await graph.query(
                """
                MERGE (community:Community {id: $community_id})
                SET community.name = $community_name,
                    community.summary = $community_summary
                """,
                {
                    "community_id": projection.community_id,
                    "community_name": projection.community_name,
                    "community_summary": projection.community_summary,
                },
            )
            await graph.query(
                """
                MATCH (community:Community {id: $community_id})
                MERGE (domain:Domain {id: $domain_id})
                SET domain.name = $domain_name,
                    domain.summary = $domain_summary,
                    domain.embedding = vecf32($domain_embedding)
                MERGE (domain)-[community_link:IN_COMMUNITY]->(community)
                SET community_link.source = 'analyst'
                """,
                {
                    "community_id": projection.community_id,
                    "domain_id": projection.domain.id,
                    "domain_name": projection.domain.name,
                    "domain_summary": projection.domain.summary,
                    "domain_embedding": projection.domain.embedding,
                },
            )
            new_concepts = [
                {
                    "id": concept.id,
                    "name": concept.name,
                    "summary": concept.summary,
                    "embedding": concept.embedding,
                    "aliases": list(concept.aliases) or [concept.name],
                }
                for concept in projection.concepts
                if concept.is_new
            ]
            if new_concepts:
                await graph.query(
                    """
                    UNWIND $concepts AS item
                    MERGE (concept:Concept {id: item.id})
                    SET concept.name = item.name,
                        concept.summary = item.summary,
                        concept.embedding = vecf32(item.embedding),
                        concept.aliases = item.aliases
                    """,
                    {"concepts": new_concepts},
                )
            existing_concepts = [
                {"id": concept.id, "aliases": list(concept.aliases)}
                for concept in projection.concepts
                if not concept.is_new and concept.aliases
            ]
            if existing_concepts:
                await graph.query(
                    """
                    UNWIND $concepts AS item
                    MATCH (concept:Concept {id: item.id})
                    UNWIND item.aliases AS alias
                    SET concept.aliases = CASE
                        WHEN concept.aliases IS NULL THEN [alias]
                        WHEN alias IN concept.aliases THEN concept.aliases
                        ELSE concept.aliases + [alias]
                    END
                    """,
                    {"concepts": existing_concepts},
                )
            concept_ids = sorted({concept.id for concept in projection.concepts})
            if concept_ids:
                await graph.query(
                    """
                    UNWIND $concept_ids AS concept_id
                    MATCH (domain:Domain {id: $domain_id})
                    MATCH (concept:Concept {id: concept_id})
                    MERGE (concept)-[domain_link:IN_DOMAIN]->(domain)
                    SET concept.card_ids = CASE
                            WHEN concept.card_ids IS NULL THEN [$card_id]
                            WHEN $card_id IN concept.card_ids THEN concept.card_ids
                            ELSE concept.card_ids + [$card_id]
                        END,
                        domain_link.card_ids = CASE
                            WHEN domain_link.card_ids IS NULL THEN [$card_id]
                            WHEN $card_id IN domain_link.card_ids
                                THEN domain_link.card_ids
                            ELSE domain_link.card_ids + [$card_id]
                        END,
                        domain_link.weight = CASE
                            WHEN domain_link.card_ids IS NULL THEN 1
                            WHEN $card_id IN domain_link.card_ids
                                THEN size(domain_link.card_ids)
                            ELSE size(domain_link.card_ids) + 1
                        END
                    """,
                    {
                        "domain_id": projection.domain.id,
                        "card_id": projection.card_id,
                        "concept_ids": concept_ids,
                    },
                )
            relations = [
                {"source_id": source_id, "target_id": target_id}
                for source_id, target_id in combinations(concept_ids, 2)
            ]
            if relations:
                await graph.query(
                    """
                    UNWIND $relations AS item
                    MATCH (source:Concept {id: item.source_id})
                    MATCH (target:Concept {id: item.target_id})
                    MERGE (source)-[relation:RELATED_TO]->(target)
                    SET relation.weight = CASE
                        WHEN relation.card_ids IS NULL THEN 1
                        WHEN $card_id IN relation.card_ids THEN size(relation.card_ids)
                        ELSE size(relation.card_ids) + 1
                    END,
                    relation.card_ids = CASE
                        WHEN relation.card_ids IS NULL THEN [$card_id]
                        WHEN $card_id IN relation.card_ids THEN relation.card_ids
                        ELSE relation.card_ids + [$card_id]
                    END
                    """,
                    {
                        "relations": relations,
                        "card_id": projection.card_id,
                    },
                )
        except Exception as exc:
            raise GraphStorageError(f"project failed: {exc}") from exc

    async def remove_cards(self, card_ids: list[str]) -> None:
        if not card_ids:
            return
        graph = self._graph()
        params = {"card_ids": list(dict.fromkeys(card_ids))}
        try:
            await graph.query(
                """
                MATCH (concept:Concept)
                WHERE any(card_id IN coalesce(concept.card_ids, [])
                          WHERE card_id IN $card_ids)
                SET concept.card_ids = [
                    card_id IN concept.card_ids
                    WHERE NOT card_id IN $card_ids
                ]
                """,
                params,
            )
            for relation_type in ("RELATED_TO", "IN_DOMAIN"):
                await graph.query(
                    f"""
                    MATCH ()-[relation:{relation_type}]->()
                    WHERE any(card_id IN coalesce(relation.card_ids, [])
                              WHERE card_id IN $card_ids)
                    WITH relation, [
                        card_id IN relation.card_ids
                        WHERE NOT card_id IN $card_ids
                    ] AS remaining
                    SET relation.card_ids = remaining,
                        relation.weight = size(remaining)
                    WITH relation, remaining
                    WHERE size(remaining) = 0
                    DELETE relation
                    """,
                    params,
                )
            await graph.query(
                """
                MATCH (concept:Concept)
                WHERE size(coalesce(concept.card_ids, [])) = 0
                DETACH DELETE concept
                """
            )
            await graph.query(
                """
                MATCH (domain:Domain)
                WHERE NOT (domain)<-[:IN_DOMAIN]-(:Concept)
                DETACH DELETE domain
                """
            )
            await graph.query(
                """
                MATCH (community:Community)
                WHERE NOT (community)<-[:IN_COMMUNITY]-()
                DELETE community
                """
            )
        except Exception as exc:
            raise GraphStorageError(f"remove_cards failed: {exc}") from exc

    async def find_similar_concepts(
        self,
        embedding: list[float],
        top_k: int = 5,
    ) -> list[dict]:
        try:
            result = await self._graph().query(
                """
                CALL db.idx.vector.queryNodes(
                    'Concept', 'embedding', $top_k, vecf32($embedding)
                )
                YIELD node, score AS distance
                RETURN node.id, node.name, node.summary, 1.0 - distance AS similarity
                ORDER BY similarity DESC
                """,
                {"top_k": top_k, "embedding": embedding},
            )
            return [
                {
                    "id": row[0],
                    "name": row[1],
                    "summary": row[2],
                    "score": row[3],
                }
                for row in result.result_set
            ]
        except Exception as exc:
            raise GraphStorageError(f"find_similar_concepts failed: {exc}") from exc

    async def traverse_from_concepts(
        self,
        concept_ids: list[str],
        hops: int = 2,
        limit: int = 100,
    ) -> list[dict]:
        if not concept_ids:
            return []
        if hops < 1 or hops > 3:
            raise ValueError("hops must be between 1 and 3")
        try:
            result = await self._graph().query(
                f"""
                MATCH (start:Concept) WHERE start.id IN $ids
                MATCH path = (start)-[:RELATED_TO*1..{hops}]-(connected:Concept)
                RETURN connected.id, connected.name, connected.summary,
                       min(length(path)) AS distance
                ORDER BY distance ASC, connected.id ASC
                LIMIT $limit
                """,
                {"ids": concept_ids, "limit": limit},
            )
            return [
                {
                    "id": row[0],
                    "name": row[1],
                    "summary": row[2],
                    "distance": row[3],
                }
                for row in result.result_set
            ]
        except Exception as exc:
            raise GraphStorageError(f"traverse_from_concepts failed: {exc}") from exc

    async def get_cards_for_concepts(
        self,
        concept_ids: list[str],
        limit: int = 100,
    ) -> list[dict]:
        if not concept_ids:
            return []
        try:
            result = await self._graph().query(
                """
                MATCH (concept:Concept)
                WHERE concept.id IN $ids
                UNWIND coalesce(concept.card_ids, []) AS card_id
                RETURN card_id, concept.id
                ORDER BY concept.id ASC, card_id ASC
                LIMIT $limit
                """,
                {"ids": concept_ids, "limit": limit},
            )
            return [
                {
                    "id": row[0],
                    "concept_id": row[1],
                    "relevance": 1.0,
                }
                for row in result.result_set
            ]
        except Exception as exc:
            raise GraphStorageError(f"get_cards_for_concepts failed: {exc}") from exc

    async def get_visual_graph(self) -> dict:
        try:
            domain_rows = (
                await self._graph().query(
                    """
                    MATCH (domain:Domain)
                    OPTIONAL MATCH (domain)-[relation:IN_COMMUNITY]->
                                   (community:Community)
                    RETURN domain.id, domain.name, domain.summary,
                           community.id, community.name, community.summary,
                           relation.source, community.active
                    ORDER BY domain.id ASC
                    """
                )
            ).result_set
            concept_rows = (
                await self._graph().query(
                    """
                    MATCH (concept:Concept)-[relation:IN_DOMAIN]->(domain:Domain)
                    RETURN concept.id, concept.name, concept.summary,
                           coalesce(concept.card_ids, []), domain.id,
                           coalesce(relation.weight, 1)
                    ORDER BY concept.id ASC, relation.weight DESC, domain.id ASC
                    """
                )
            ).result_set
            edge_rows = (
                await self._graph().query(
                    """
                    MATCH (source:Concept)-[relation:RELATED_TO]-(target:Concept)
                    WHERE source.id < target.id
                    RETURN source.id, target.id, relation.weight
                    ORDER BY source.id ASC, target.id ASC
                    """
                )
            ).result_set
            domains: dict[str, dict] = {}
            for row in domain_rows:
                domain = domains.setdefault(
                    row[0],
                    {
                        "id": row[0],
                        "name": row[1],
                        "summary": row[2],
                        "communities": [],
                    },
                )
                if row[3] is not None:
                    domain["communities"].append(
                        {
                            "id": row[3],
                            "name": row[4],
                            "summary": row[5],
                            "source": row[6],
                            "active": row[7],
                        }
                    )
            concepts: dict[str, dict] = {}
            for row in concept_rows:
                concept = concepts.setdefault(
                    row[0],
                    {
                        "id": row[0],
                        "name": row[1],
                        "summary": row[2],
                        "card_ids": row[3],
                        "domains": [],
                    },
                )
                concept["domains"].append({"id": row[4], "weight": row[5]})
            return {
                "domains": list(domains.values()),
                "concepts": list(concepts.values()),
                "edges": [
                    {"source_id": row[0], "target_id": row[1], "weight": row[2]}
                    for row in edge_rows
                ],
            }
        except Exception as exc:
            raise GraphStorageError(f"get_visual_graph failed: {exc}") from exc

    async def get_card_ids_for_concept(
        self,
        concept_id: str,
    ) -> list[str] | None:
        try:
            result = await self._graph().query(
                """
                MATCH (concept:Concept {id: $concept_id})
                RETURN coalesce(concept.card_ids, [])
                """,
                {"concept_id": concept_id},
            )
            if not result.result_set:
                return None
            return list(result.result_set[0][0])
        except Exception as exc:
            raise GraphStorageError(f"get_card_ids_for_concept failed: {exc}") from exc

    async def get_concept_neighbors(
        self,
        concept_ids: list[str],
        per_concept: int = 8,
    ) -> list[dict]:
        if not concept_ids:
            return []
        try:
            result = await self._graph().query(
                """
                MATCH (source:Concept)-[relation:RELATED_TO]-(target:Concept)
                WHERE source.id IN $ids AND NOT target.id IN $ids
                WITH source, target, relation
                ORDER BY source.id ASC, relation.weight DESC, target.id ASC
                WITH source, collect([
                    target.id, target.name, target.summary, relation.weight
                ])[0..$per_concept] AS neighbors
                UNWIND neighbors AS neighbor
                RETURN source.id, neighbor[0], neighbor[1], neighbor[2], neighbor[3]
                """,
                {"ids": concept_ids, "per_concept": per_concept},
            )
            return [
                {
                    "source_id": row[0],
                    "id": row[1],
                    "name": row[2],
                    "summary": row[3],
                    "weight": row[4],
                }
                for row in result.result_set
            ]
        except Exception as exc:
            raise GraphStorageError(f"get_concept_neighbors failed: {exc}") from exc

    async def detect_communities(self, max_iterations: int = 10) -> list[dict]:
        try:
            result = await self._graph().query(
                """
                CALL algo.labelPropagation({
                    nodeLabels: ['Concept'],
                    relationshipTypes: ['RELATED_TO'],
                    maxIterations: $max_iterations
                })
                YIELD node, communityId
                RETURN communityId, collect(node.id), collect(node.name),
                       collect(node.summary), count(node) AS community_size
                ORDER BY community_size DESC, communityId ASC
                """,
                {"max_iterations": max_iterations},
            )
            return [
                {
                    "id": row[0],
                    "concepts": [
                        {"id": concept_id, "name": name, "summary": summary}
                        for concept_id, name, summary in zip(
                            row[1], row[2], row[3], strict=True
                        )
                    ],
                }
                for row in result.result_set
            ]
        except Exception as exc:
            raise GraphStorageError(f"detect_communities failed: {exc}") from exc

    async def apply_communities(
        self,
        communities: list[GraphCommunity],
    ) -> None:
        graph = self._graph()
        try:
            await graph.query(
                """
                MATCH (:Concept)-[relation:IN_COMMUNITY]->(community:Community)
                WHERE community.source = 'clusterizer'
                DELETE relation
                """
            )
            await graph.query(
                """
                MATCH (:Domain)-[relation:IN_COMMUNITY]->(community:Community)
                WHERE relation.source = 'clusterizer'
                DELETE relation
                """
            )
            await graph.query(
                """
                MATCH (community:Community)
                WHERE community.source = 'clusterizer'
                SET community.active = false
                """
            )
            if not communities:
                return
            payload = [
                {
                    "id": community.id,
                    "name": community.name,
                    "summary": community.summary,
                    "concept_ids": list(community.concept_ids),
                }
                for community in communities
            ]
            await graph.query(
                """
                UNWIND $communities AS item
                MERGE (community:Community {id: item.id})
                SET community.name = item.name,
                    community.summary = item.summary,
                    community.source = 'clusterizer',
                    community.active = true
                WITH community, item
                UNWIND item.concept_ids AS concept_id
                MATCH (concept:Concept {id: concept_id})
                MERGE (concept)-[relation:IN_COMMUNITY]->(community)
                SET relation.source = 'clusterizer'
                """,
                {"communities": payload},
            )
            await graph.query(
                """
                MATCH (domain:Domain)<-[:IN_DOMAIN]-(concept:Concept)
                      -[:IN_COMMUNITY]->(community:Community)
                WHERE community.source = 'clusterizer'
                MERGE (domain)-[relation:IN_COMMUNITY]->(community)
                SET relation.source = 'clusterizer'
                """
            )
        except Exception as exc:
            raise GraphStorageError(f"apply_communities failed: {exc}") from exc
