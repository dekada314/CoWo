import enum


class JobStatus(str, enum.Enum):
    QUEUED = "queud"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ProcessingStage(str, enum.Enum):
    UPLOADED = "uploaded"
    EXTRACTION = "extraction"
    CHUNKING = "chunking"
    EMBEDDING = "embedding"
    INDEXING = "indexing"
    GRAPH_EXTRACTION = "graph_extraction"
    GRAPH_INDEXING = "graph_indexing"


class AgentRunStatus(str, enum.Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    INTERRUPTED = "interrupted"
