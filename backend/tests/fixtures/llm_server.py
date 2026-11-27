"""Deterministic local LLM stub for the opt-in container integration test only."""

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if self.path.endswith("/embeddings"):
            inputs = body["input"]
            dimensions = body.get("dimensions", 1024)
            vectors = []
            for value in inputs:
                lowered = value.casefold()
                if "chunk" in lowered:
                    vector = [1.0, 0.0, *([0.0] * (dimensions - 2))]
                elif "context" in lowered:
                    vector = [0.8, 0.6, *([0.0] * (dimensions - 2))]
                else:
                    vector = [0.0, 1.0, *([0.0] * (dimensions - 2))]
                vectors.append(vector)
            data = []
            for index, vector in enumerate(vectors):
                item = {"embedding": vector}
                if index:
                    item["index"] = index
                data.append(item)
            response = {"data": data}
        elif "Name and summarize" in body["messages"][0]["content"]:
            data = {
                "name": "Retrieval systems",
                "summary": "Concepts related to retrieval and chunking.",
            }
            response = {
                "choices": [
                    {"finish_reason": "stop", "message": {"content": json.dumps(data)}}
                ]
            }
        elif "Answer only from" in body["messages"][0]["content"]:
            request = json.loads(body["messages"][1]["content"])
            data = {
                "answer": "Chunking preserves context in the test documents.",
                "cited_job_ids": [request["sources"][0]["job_id"]],
            }
            response = {
                "choices": [
                    {"finish_reason": "stop", "message": {"content": json.dumps(data)}}
                ]
            }
        elif "Summarize the evidence" in body["messages"][0]["content"]:
            data = {"summary": "Test evidence", "concepts": ["Chunking"]}
            response = {
                "choices": [
                    {"finish_reason": "stop", "message": {"content": json.dumps(data)}}
                ]
            }
        else:
            data = {
                "summary": "Integration test card (stub model)",
                "key_points": ["Document analyzed by the test pipeline"],
                "community": {"name": "Computing", "description": "Test community"},
                "domain": {"name": "RAG", "description": "Test domain"},
                "concepts": [
                    {"name": "Chunking", "description": "Test concept"},
                    {"name": "Context Windows", "description": "Test context"},
                    {"name": "Retrieval", "description": "Test retrieval"},
                ],
            }
            response = {
                "choices": [
                    {"finish_reason": "stop", "message": {"content": json.dumps(data)}}
                ]
            }
        encoded = json.dumps(response).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
