from typing import Any

from falkordb.asyncio import FalkorDB

from src.core.settings import FalkorDBSettings


class FalkorDBStorage:
    def __init__(self, client: FalkorDB, config: FalkorDBSettings) -> None:
        self._client = client
        self._config = config

    @property
    def _graph(self):
        return self._client.select_graph(self._config.graph_name)

    async def create_concept(
        self,
        name: str,
        description: str,
        embedding: list[float],
        domain_id: str | None = None,
    ) -> str:
        query = """
        CREATE (c:Concept {
            name: $name,
            description: $description,
            embedding: vecf32($embedding),
            domain_id: $domain_id
        })
        RETURN id(c)
        """
        result = await self._graph.query(
            query,
            {
                "name": name,
                "description": description,
                "embedding": embedding,
                "domain_id": domain_id,
            },
        )
        return str(result.result_set[0][0])

    async def get_concept(self, concept_id: str) -> dict | None:
        query = "MATCH (c:Concept) WHERE id(c) = $id RETURN c"
        result = await self._graph.query(query, {"id": int(concept_id)})
        if not result.result_set:
            return None
        node = result.result_set[0][0]
        return dict(node.properties)

    async def find_similar_concepts(
        self,
        embedding: list[float],
        top_k: int = 5,
    ) -> list[dict]:
        query = """
        CALL db.idx.vector.queryNodes('Concept', 'embedding', $k, vecf32($vec))
        YIELD node, score
        RETURN node.name, node.description, node.domain_id, score
        ORDER BY score DESC
        """
        result = await self._graph.query(query, {"k": top_k, "vec": embedding})
        return [
            {
                "name": row[0],
                "description": row[1],
                "domain_id": row[2],
                "score": row[3],
            }
            for row in result.result_set
        ]

    async def create_relation(
        self,
        source_id: str,
        target_id: str,
        weight: float = 1.0,
    ) -> None:
        query = """
        MATCH (a:Concept) WHERE id(a) = $source_id
        MATCH (b:Concept) WHERE id(b) = $target_id
        MERGE (a)-[r:RELATED_TO]->(b)
        SET r.weight = $weight
        """
        await self._graph.query(
            query,
            {
                "source_id": int(source_id),
                "target_id": int(target_id),
                "weight": weight,
            },
        )

    async def link_card_to_concept(
        self,
        card_id: str,
        concept_id: str,
        relevance: float = 1.0,
    ) -> None:
        query = """
        MATCH (card:Card) WHERE id(card) = $card_id
        MATCH (c:Concept) WHERE id(c) = $concept_id
        MERGE (card)-[r:MENTIONS]->(c)
        SET r.relevance = $relevance
        """
        await self._graph.query(
            query,
            {
                "card_id": int(card_id),
                "concept_id": int(concept_id),
                "relevance": relevance,
            },
        )

    async def traverse_from_concepts(
        self,
        concept_ids: list[str],
        hops: int = 2,
    ) -> dict:
        query = f"""
        MATCH (start:Concept) WHERE id(start) IN $ids
        MATCH path = (start)-[:RELATED_TO*1..{hops}]-(connected:Concept)
        RETURN DISTINCT id(connected), connected.name, connected.description, length(path) AS distance
        """
        result = await self._graph.query(query, {"ids": [int(cid) for cid in concept_ids]})
        concepts = [
            {
                "id": str(row[0]),
                "name": row[1],
                "description": row[2],
                "distance": row[3],
            }
            for row in result.result_set
        ]
        return {"concepts": concepts}

    async def get_cards_for_concepts(
        self,
        concept_ids: list[str],
    ) -> list[dict]:
        query = """
        MATCH (c:Concept) WHERE id(c) IN $ids
        MATCH (card:Card)-[:MENTIONS]->(c)
        RETURN DISTINCT id(card), card.summary, card.document_id
        """
        result = await self._graph.query(query, {"ids": [int(cid) for cid in concept_ids]})
        return [
            {
                "id": str(row[0]),
                "summary": row[1],
                "document_id": row[2],
            }
            for row in result.result_set
        ]

    async def create_card(
        self,
        summary: str,
        document_id: str,
        key_points: list[str],
    ) -> str:
        query = """
        CREATE (card:Card {
            summary: $summary,
            document_id: $document_id,
            key_points: $key_points
        })
        RETURN id(card)
        """
        result = await self._graph.query(
            query,
            {
                "summary": summary,
                "document_id": document_id,
                "key_points": key_points,
            },
        )
        return str(result.result_set[0][0])

    async def create_vector_index(
        self,
        label: str = "Concept",
        attribute: str = "embedding",
        dimension: int = 768,
        similarity: str = "cosine",
    ) -> None:
        query = f"""
        CREATE VECTOR INDEX FOR (n:{label}) ON (n.{attribute})
        OPTIONS {{dimension: {dimension}, similarityFunction: '{similarity}'}}
        """
        await self._graph.query(query)