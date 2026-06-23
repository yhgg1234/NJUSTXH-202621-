"""知识图谱 REST API。"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.graph.dependencies import get_graph_service
from app.graph.models import (
    GraphImportRequest,
    GraphImportResult,
    GraphNode,
    GraphRelationship,
    SubgraphResponse,
)
from app.graph.service import GraphService, MissingEndpointError

router = APIRouter(prefix="/api/graph", tags=["knowledge-graph"])
Service = Annotated[GraphService, Depends(get_graph_service)]


@router.post("/schema", status_code=status.HTTP_201_CREATED)
def initialize_schema(service: Service) -> dict[str, Any]:
    statements = service.initialize_schema()
    return {"status": "ready", "statements_applied": len(statements)}


@router.post("/import", response_model=GraphImportResult)
def import_graph(payload: GraphImportRequest, service: Service) -> GraphImportResult:
    try:
        return service.import_graph(payload)
    except MissingEndpointError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": str(exc), "missing_node_ids": sorted(exc.node_ids)},
        ) from exc


@router.put("/nodes/{node_id}")
def upsert_node(node_id: str, payload: GraphNode, service: Service) -> dict[str, Any]:
    if node_id != payload.id:
        raise HTTPException(status_code=422, detail="path node_id must equal payload.id")
    return {"nodes_upserted": service.upsert_node(payload)}


@router.put("/relationships/{relationship_id}")
def upsert_relationship(
    relationship_id: str, payload: GraphRelationship, service: Service
) -> dict[str, Any]:
    if relationship_id != payload.id:
        raise HTTPException(status_code=422, detail="path relationship_id must equal payload.id")
    try:
        return {"relationships_upserted": service.upsert_relationship(payload)}
    except MissingEndpointError as exc:
        raise HTTPException(
            status_code=422,
            detail={"message": str(exc), "missing_node_ids": sorted(exc.node_ids)},
        ) from exc


@router.get("/subgraph", response_model=SubgraphResponse)
def get_subgraph(
    service: Service,
    job_id: str | None = None,
    tech_stack: str | None = None,
    level: str | None = None,
    industry: str | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> SubgraphResponse:
    result = service.get_subgraph(
        job_id=job_id,
        tech_stack=tech_stack,
        level=level,
        industry=industry,
        limit=limit,
    )
    return SubgraphResponse(**result, truncated=len(result["nodes"]) >= limit)


@router.get("/stats")
def get_stats(service: Service) -> dict[str, Any]:
    return service.get_stats()
