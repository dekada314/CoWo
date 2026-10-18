from dependency_injector import resources
from falkordb.asyncio import FalkorDB


class ResourceFalkorClient(resources.AsyncResource):
    async def init(
        self, host: str, port: int, username: str | None, password: str | None
    ):
        client = FalkorDB(
            host=host, port=port, username=username, password=password
        )
        await client.connection.ping()
        return client

    async def shutdown(self, client: FalkorDB) -> None:
        if client:
            await client.close()
