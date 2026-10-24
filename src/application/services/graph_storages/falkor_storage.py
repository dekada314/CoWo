from typing import Any

from falkordb.asyncio import FalkorDB
from src.domain.exceptions import GraphStorageError


class FalkorDBStorage:
    def __init__(self, client: FalkorDB, graph_name: str):
        self._client = client
        self._graph_name = graph_name

    def _graph(self):
        return self._client.select_graph(self._graph_name)

    async def _create_node(
        self,
        label: str,
        properties: dict[str, Any],
    ) -> str:
        graph = self._graph()
        props = ", ".join(f"{key}: ${key}" for key in properties)
        query = f"CREATE (n:{label} {{{props}}}) RETURN id(n)"
        result = await graph.query(query, properties)
        return str(result.result_set[0][0])

    async def _create_link(
        self,
        source_label: str,
        source_id: str,
        target_label: str,
        target_id: str,
        relation: str,
        properties: dict[str, Any] | None = None,
    ) -> None:
        graph = self._graph()
        set_clause = ""
        params: dict[str, Any] = {
            "source_id": int(source_id),
            "target_id": int(target_id),
        }
        if properties:
            assignments = ", ".join(f"r.{key} = ${key}" for key in properties)
            set_clause = f"SET {assignments}"
            params.update(properties)

        query = f"""
        MATCH (a:{source_label}) WHERE id(a) = $source_id
        MATCH (b:{target_label}) WHERE id(b) = $target_id
        MERGE (a)-[r:{relation}]->(b)
        {set_clause}
        """
        await graph.query(query, params)

    async def _get_node_by_id(
        self,
        label: str,
        node_id: str,
        fields: list[str],
    ) -> dict | None:
        graph = self._graph()
        field_list = ", ".join(f"n.{field}" for field in fields)
        query = f"""
        MATCH (n:{label}) WHERE id(n) = $id
        RETURN id(n), {field_list}
        """
        result = await graph.query(query, {"id": int(node_id)})
        if not result.result_set:
            return None
        row = result.result_set[0]
        record = {"id": str(row[0])}
        for index, field in enumerate(fields, start=1):
            record[field] = row[index]
        return record

    async def _vector_search(
        self,
        label: str,
        embedding: list[float],
        top_k: int,
        fields: list[str],
    ) -> list[dict]:
        graph = self._graph()
        field_list = ", ".join(f"node.{field}" for field in fields)
        query = f"""
        CALL db.idx.vector.queryNodes('{label}', 'embedding', $k, vecf32($vec))
        YIELD node, score
        RETURN id(node), {field_list}, score
        ORDER BY score DESC
        """
        result = await graph.query(query, {"k": top_k, "vec": embedding})
        records: list[dict] = []
        for row in result.result_set:
            record = {"id": str(row[0])}
            for index, field in enumerate(fields, start=1):
                record[field] = row[index]
            record["score"] = row[len(fields) + 1]
            records.append(record)
        return records

    async def _collect_by_relation(
        self,
        source_label: str,
        source_ids: list[str],
        target_label: str,
        relation: str,
        fields: list[str],
    ) -> list[dict]:
        if not source_ids:
            return []
        graph = self._graph()
        field_list = ", ".join(f"target.{field}" for field in fields)
        query = f"""
        MATCH (source:{source_label}) WHERE id(source) IN $ids
        MATCH (source)-[:{relation}]->(target:{target_label})
        RETURN DISTINCT id(target), {field_list}
        """
        result = await graph.query(
            query, {"ids": [int(sid) for sid in source_ids]}
        )
        records: list[dict] = []
        for row in result.result_set:
            record = {"id": str(row[0])}
            for index, field in enumerate(fields, start=1):
                record[field] = row[index]
            records.append(record)
        return records

    async def create_domain(
        self,
        name: str,
        summary: str,
        embedding: list[float],
    ) -> str:
        try:
            return await self._create_node(
                "Domain",
                {"name": name, "summary": summary, "embedding": embedding},
            )
        except Exception as exc:
            raise GraphStorageError(f"create_domain failed: {exc}") from exc

    async def get_domain_by_id(self, domain_id: str) -> dict | None:
        try:
            return await self._get_node_by_id(
                "Domain", domain_id, ["name", "summary"]
            )
        except Exception as exc:
            raise GraphStorageError(f"get_domain_by_id failed: {exc}") from exc

    async def find_similar_domains(
        self,
        embedding: list[float],
        top_k: int = 3,
    ) -> list[dict]:
        try:
            return await self._vector_search(
                "Domain", embedding, top_k, ["name", "summary"]
            )
        except Exception as exc:
            raise GraphStorageError(
                f"find_similar_domains failed: {exc}"
            ) from exc

    async def create_concept(
        self,
        name: str,
        summary: str,
        embedding: list[float],
        domain_id: str | None = None,
    ) -> str:
        try:
            concept_id = await self._create_node(
                "Concept",
                {"name": name, "summary": summary, "embedding": embedding},
            )
            if domain_id is not None:
                await self.link_concept_to_domain(concept_id, domain_id)
            return concept_id
        except GraphStorageError:
            raise
        except Exception as exc:
            raise GraphStorageError(f"create_concept failed: {exc}") from exc

    async def get_concept_by_id(self, concept_id: str) -> dict | None:
        try:
            return await self._get_node_by_id(
                "Concept", concept_id, ["name", "summary"]
            )
        except Exception as exc:
            raise GraphStorageError(f"get_concept_by_id failed: {exc}") from exc

    async def find_similar_concepts(
        self,
        embedding: list[float],
        top_k: int = 5,
    ) -> list[dict]:
        try:
            return await self._vector_search(
                "Concept", embedding, top_k, ["name", "summary"]
            )
        except Exception as exc:
            raise GraphStorageError(
                f"find_similar_concepts failed: {exc}"
            ) from exc

    async def create_card(
        self,
        summary: str,
        document_id: str,
        key_points: list[str],
    ) -> str:
        try:
            return await self._create_node(
                "Card",
                {
                    "summary": summary,
                    "document_id": document_id,
                    "key_points": key_points,
                },
            )
        except Exception as exc:
            raise GraphStorageError(f"create_card failed: {exc}") from exc

    async def get_card_by_id(self, card_id: str) -> dict | None:
        try:
            return await self._get_node_by_id(
                "Card", card_id, ["summary", "document_id", "key_points"]
            )
        except Exception as exc:
            raise GraphStorageError(f"get_card_by_id failed: {exc}") from exc

    async def create_chunk(
        self,
        text: str,
        embedding: list[float],
        card_id: str,
        index: int,
    ) -> str:
        try:
            chunk_id = await self._create_node(
                "Chunk",
                {"text": text, "embedding": embedding, "index": index},
            )
            await self.link_chunk_to_card(chunk_id, card_id)
            return chunk_id
        except GraphStorageError:
            raise
        except Exception as exc:
            raise GraphStorageError(f"create_chunk failed: {exc}") from exc

    async def find_similar_chunks(
        self,
        embedding: list[float],
        top_k: int = 10,
    ) -> list[dict]:
        try:
            return await self._vector_search(
                "Chunk", embedding, top_k, ["text", "index"]
            )
        except Exception as exc:
            raise GraphStorageError(
                f"find_similar_chunks failed: {exc}"
            ) from exc

    async def get_chunks_for_card(self, card_id: str) -> list[dict]:
        try:
            graph = self._graph()
            query = """
            MATCH (ch:Chunk)-[:PART_OF]->(card:Card) WHERE id(card) = $id
            RETURN id(ch), ch.text, ch.index
            ORDER BY ch.index ASC
            """
            result = await graph.query(query, {"id": int(card_id)})
            return [
                {"id": str(row[0]), "text": row[1], "index": row[2]}
                for row in result.result_set
            ]
        except Exception as exc:
            raise GraphStorageError(
                f"get_chunks_for_card failed: {exc}"
            ) from exc

    async def create_relation(
        self,
        source_id: str,
        target_id: str,
        weight: float = 1.0,
    ) -> None:
        try:
            await self._create_link(
                "Concept",
                source_id,
                "Concept",
                target_id,
                "RELATED_TO",
                {"weight": weight},
            )
        except Exception as exc:
            raise GraphStorageError(f"create_relation failed: {exc}") from exc

    async def link_card_to_concept(
        self,
        card_id: str,
        concept_id: str,
        relevance: float = 1.0,
    ) -> None:
        try:
            await self._create_link(
                "Card",
                card_id,
                "Concept",
                concept_id,
                "MENTIONS",
                {"relevance": relevance},
            )
        except Exception as exc:
            raise GraphStorageError(
                f"link_card_to_concept failed: {exc}"
            ) from exc

    async def link_concept_to_domain(
        self,
        concept_id: str,
        domain_id: str,
        relevance: float = 1.0,
    ) -> None:
        try:
            await self._create_link(
                "Concept",
                concept_id,
                "Domain",
                domain_id,
                "IN_DOMAIN",
                {"relevance": relevance},
            )
        except Exception as exc:
            raise GraphStorageError(
                f"link_concept_to_domain failed: {exc}"
            ) from exc

    async def link_chunk_to_card(
        self,
        chunk_id: str,
        card_id: str,
    ) -> None:
        try:
            await self._create_link(
                "Chunk",
                chunk_id,
                "Card",
                card_id,
                "PART_OF",
            )
        except Exception as exc:
            raise GraphStorageError(
                f"link_chunk_to_card failed: {exc}"
            ) from exc

    async def traverse_from_concepts(
        self,
        concept_ids: list[str],
        hops: int = 2,
    ) -> dict:
        try:
            if not concept_ids:
                return {"concepts": []}
            if hops < 1 or hops > 3:
                raise ValueError("hops must be between 1 and 3")

            graph = self._graph()
            query = f"""
            MATCH (start:Concept) WHERE id(start) IN $ids
            MATCH path = (start)-[:RELATED_TO*1..{hops}]-(connected:Concept)
            RETURN DISTINCT id(connected), connected.name, connected.summary,
                   length(path) AS distance
            ORDER BY distance ASC
            """
            result = await graph.query(
                query, {"ids": [int(cid) for cid in concept_ids]}
            )
            return {
                "concepts": [
                    {
                        "id": str(row[0]),
                        "name": row[1],
                        "summary": row[2],
                        "distance": row[3],
                    }
                    for row in result.result_set
                ]
            }
        except ValueError:
            raise
        except Exception as exc:
            raise GraphStorageError(
                f"traverse_from_concepts failed: {exc}"
            ) from exc

    async def get_cards_for_concepts(
        self,
        concept_ids: list[str],
    ) -> list[dict]:
        try:
            return await self._collect_by_relation(
                "Concept",
                concept_ids,
                "Card",
                "MENTIONS",
                ["summary", "document_id"],
            )
        except Exception as exc:
            raise GraphStorageError(
                f"get_cards_for_concepts failed: {exc}"
            ) from exc

    async def get_domains_for_concepts(
        self,
        concept_ids: list[str],
    ) -> list[dict]:
        try:
            return await self._collect_by_relation(
                "Concept",
                concept_ids,
                "Domain",
                "IN_DOMAIN",
                ["name", "summary"],
            )
        except Exception as exc:
            raise GraphStorageError(
                f"get_domains_for_concepts failed: {exc}"
            ) from exc

    async def ensure_vector_indexes(self, dimension: int = 768) -> None:
        try:
            graph = self._graph()
            for label in ("Domain", "Concept", "Chunk"):
                query = f"""
                CREATE VECTOR INDEX FOR (n:{label}) ON (n.embedding)
                OPTIONS {{dimension: {dimension}, similarityFunction: 'cosine'}}
                """
                try:
                    await graph.query(query)
                except Exception:
                    pass
        except Exception as exc:
            raise GraphStorageError(
                f"ensure_vector_indexes failed: {exc}"
            ) from exc
