import asyncio
import os
from uuid import uuid4

import pytest
from falkordb.asyncio import FalkorDB

from src.application.services.graph_storages.falkor_storage import FalkorDBStorage

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.getenv("COWO_TEST_FALKOR_PORT"),
        reason="configure a disposable FalkorDB integration server",
    ),
]


def test_card_removal_recalculates_graph_and_removes_orphans():
    async def scenario():
        client = FalkorDB(
            host="127.0.0.1",
            port=int(os.environ["COWO_TEST_FALKOR_PORT"]),
        )
        graph_name = "cowo_test_" + uuid4().hex
        graph = client.select_graph(graph_name)
        storage = FalkorDBStorage(client, graph_name)
        try:
            await graph.query(
                """
                CREATE (community:Community {id: 'community'})
                CREATE (domain:Domain {id: 'domain'})
                CREATE (first:Concept {
                    id: 'first', card_ids: ['remove', 'keep']
                })
                CREATE (second:Concept {
                    id: 'second', card_ids: ['remove']
                })
                CREATE (first)-[:IN_DOMAIN {
                    card_ids: ['remove', 'keep'], weight: 2
                }]->(domain)
                CREATE (second)-[:IN_DOMAIN {
                    card_ids: ['remove'], weight: 1
                }]->(domain)
                CREATE (first)-[:RELATED_TO {
                    card_ids: ['remove'], weight: 1
                }]->(second)
                CREATE (domain)-[:IN_COMMUNITY]->(community)
                """
            )

            await storage.remove_cards(["remove"])

            concepts = (
                await graph.query(
                    """
                    MATCH (concept:Concept)-[relation:IN_DOMAIN]->(:Domain)
                    RETURN concept.id, concept.card_ids, relation.weight
                    """
                )
            ).result_set
            assert concepts == [["first", ["keep"], 1]]
            assert (
                await graph.query("MATCH ()-[r:RELATED_TO]->() RETURN count(r)")
            ).result_set == [[0]]

            await storage.remove_cards(["keep"])

            counts = (
                await graph.query(
                    """
                    MATCH (node)
                    RETURN count(node)
                    """
                )
            ).result_set
            assert counts == [[0]]
        finally:
            await graph.delete()
            await client.aclose()

    asyncio.run(scenario())
