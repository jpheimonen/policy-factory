"""Ideas router — REST endpoints for the idea pipeline.

Provides endpoints for:
- Human idea submission (POST /)
- AI idea generation (POST /generate)
- Idea listing with filtering/sorting (GET /)
- Idea detail with scores and critics (GET /:idea_id)
- Idea archiving (PUT /:idea_id/archive)
- Re-evaluation trigger (POST /:idea_id/evaluate)

All endpoints require JWT authentication. Long-running operations
(evaluation, generation) run as background asyncio tasks and return
immediately.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from policy_factory.server.deps import (
    get_current_user,
    get_data_dir,
    get_event_emitter,
    get_store,
)
from policy_factory.store.auth import UserPublic

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ideas", tags=["ideas"])


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class SubmitIdeaRequest(BaseModel):
    """Request body for submitting a human idea."""

    text: str
    target_objective: str | None = None


class SubmitIdeaResponse(BaseModel):
    """Response after submitting an idea."""

    id: str
    status: str


class GenerateIdeasRequest(BaseModel):
    """Request body for triggering AI idea generation."""

    target_objective: str | None = None


class GenerateIdeasResponse(BaseModel):
    """Response after triggering idea generation."""

    message: str


class IdeaSummaryResponse(BaseModel):
    """Summary of an idea for list responses."""

    id: str
    text: str  # May be truncated for preview
    source: str
    target_objective: str | None
    status: str
    submitted_at: str
    submitted_by: str
    overall_score: float | None


class IdeaDetailResponse(BaseModel):
    """Full idea detail including scores, critics, and synthesis."""

    id: str
    text: str
    source: str
    target_objective: str | None
    status: str
    submitted_at: str
    submitted_by: str
    evaluation_started_at: str | None
    evaluation_completed_at: str | None
    scores: dict[str, float] | None
    critic_assessments: list[dict[str, Any]]
    synthesis: dict[str, Any] | None


class ArchiveResponse(BaseModel):
    """Response after archiving an idea."""

    id: str
    status: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/", response_model=SubmitIdeaResponse, status_code=status.HTTP_201_CREATED)
async def submit_idea(
    req: SubmitIdeaRequest,
    current_user: Annotated[UserPublic, Depends(get_current_user)],
) -> SubmitIdeaResponse:
    """Submit a human idea.

    Creates the idea record and launches evaluation as a background task.
    Returns the idea ID immediately.
    """
    from policy_factory.events import IdeaSubmitted

    store = get_store()
    emitter = get_event_emitter()
    data_dir = get_data_dir()

    # Create the idea record
    idea_id = store.create_idea(
        text=req.text,
        source="human",
        target_objective=req.target_objective,
        submitted_by=current_user.email,
    )

    # Emit submission event
    await emitter.emit(IdeaSubmitted(idea_id=idea_id, source="human"))

    # Launch evaluation as a background task
    async def _background_eval() -> None:
        try:
            from policy_factory.ideas.evaluator import evaluate_idea

            await evaluate_idea(idea_id, store, emitter, data_dir)
        except Exception:
            logger.exception("Background evaluation failed for idea %s", idea_id)

    asyncio.create_task(_background_eval())

    return SubmitIdeaResponse(id=idea_id, status="pending")


@router.post("/generate", response_model=GenerateIdeasResponse)
async def trigger_generation(
    current_user: Annotated[UserPublic, Depends(get_current_user)],
    req: GenerateIdeasRequest | None = None,
) -> GenerateIdeasResponse:
    """Trigger AI idea generation.

    Launches the generation agent as a background task.
    Returns immediately with a confirmation.
    """
    store = get_store()
    emitter = get_event_emitter()
    data_dir = get_data_dir()

    target = req.target_objective if req else None

    # Launch generation as a background task
    async def _background_generate() -> None:
        try:
            from policy_factory.ideas.generator import generate_ideas

            await generate_ideas(
                store=store,
                emitter=emitter,
                data_dir=data_dir,
                target_objective=target,
                auto_evaluate=True,
            )
        except Exception:
            logger.exception("Background idea generation failed")

    asyncio.create_task(_background_generate())

    return GenerateIdeasResponse(message="Idea generation started")


@router.get("/", response_model=list[IdeaSummaryResponse])
async def list_ideas(
    current_user: Annotated[UserPublic, Depends(get_current_user)],
    idea_status: str | None = None,
    sort: str = "submitted_at",
    order: str = "desc",
    limit: int = 50,
    offset: int = 0,
) -> list[IdeaSummaryResponse]:
    """List ideas with optional filtering, sorting, and pagination.

    Args:
        idea_status: Filter by status (pending, evaluating, evaluated, archived).
        sort: Sort field — ``submitted_at`` (default) or ``score``.
        order: Sort order — ``asc`` or ``desc`` (default).
        limit: Max results (default 50, max 200).
        offset: Pagination offset.
    """
    store = get_store()

    # Clamp limits
    limit = max(1, min(limit, 200))
    offset = max(0, offset)

    # Map query param to store sort field
    sort_by = "submitted_at"
    if sort == "score":
        sort_by = "score"
    elif sort == "status":
        sort_by = "status"

    ideas = store.list_ideas(
        status=idea_status,
        sort_by=sort_by,
        sort_order=order,
        limit=limit,
        offset=offset,
    )

    # Build response with optional scores
    results: list[IdeaSummaryResponse] = []
    for idea in ideas:
        # Get overall score if available
        overall_score: float | None = None
        scores = store.get_scores(idea.id)
        if scores:
            overall_score = scores.overall_score

        # Truncate text for preview (first 200 chars)
        preview_text = idea.text[:200] + ("..." if len(idea.text) > 200 else "")

        results.append(
            IdeaSummaryResponse(
                id=idea.id,
                text=preview_text,
                source=idea.source,
                target_objective=idea.target_objective,
                status=idea.status,
                submitted_at=idea.submitted_at.isoformat(),
                submitted_by=idea.submitted_by,
                overall_score=overall_score,
            )
        )

    return results


@router.get("/{idea_id}", response_model=IdeaDetailResponse)
async def get_idea_detail(
    idea_id: str,
    current_user: Annotated[UserPublic, Depends(get_current_user)],
) -> IdeaDetailResponse:
    """Get full idea detail with scores, critic assessments, and synthesis."""
    store = get_store()

    idea = store.get_idea(idea_id)
    if idea is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Idea not found: {idea_id}",
        )

    # Get scores
    scores_dict: dict[str, float] | None = None
    scores = store.get_scores(idea_id)
    if scores:
        scores_dict = {
            "strategic_fit": scores.strategic_fit,
            "feasibility": scores.feasibility,
            "cost": scores.cost,
            "risk": scores.risk,
            "public_acceptance": scores.public_acceptance,
            "international_impact": scores.international_impact,
            "overall_score": scores.overall_score,
        }

    # Get critic assessments
    critic_results = store.get_critic_results_for_idea(idea_id)
    critic_assessments = [
        {
            "archetype": cr.archetype,
            "assessment_text": cr.assessment_text,
            "structured_assessment": cr.structured_assessment,
            "created_at": cr.created_at.isoformat(),
        }
        for cr in critic_results
    ]

    # Get synthesis
    synthesis: dict[str, Any] | None = None
    synthesis_result = store.get_synthesis_result_for_idea(idea_id)
    if synthesis_result:
        synthesis = {
            "synthesis_text": synthesis_result.synthesis_text,
            "structured_synthesis": synthesis_result.structured_synthesis,
            "created_at": synthesis_result.created_at.isoformat(),
        }

    return IdeaDetailResponse(
        id=idea.id,
        text=idea.text,
        source=idea.source,
        target_objective=idea.target_objective,
        status=idea.status,
        submitted_at=idea.submitted_at.isoformat(),
        submitted_by=idea.submitted_by,
        evaluation_started_at=(
            idea.evaluation_started_at.isoformat()
            if idea.evaluation_started_at
            else None
        ),
        evaluation_completed_at=(
            idea.evaluation_completed_at.isoformat()
            if idea.evaluation_completed_at
            else None
        ),
        scores=scores_dict,
        critic_assessments=critic_assessments,
        synthesis=synthesis,
    )


@router.put("/{idea_id}/archive", response_model=ArchiveResponse)
async def archive_idea(
    idea_id: str,
    current_user: Annotated[UserPublic, Depends(get_current_user)],
) -> ArchiveResponse:
    """Archive an idea."""
    store = get_store()

    idea = store.get_idea(idea_id)
    if idea is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Idea not found: {idea_id}",
        )

    store.archive_idea(idea_id)

    return ArchiveResponse(id=idea_id, status="archived")


@router.post("/{idea_id}/evaluate")
async def retrigger_evaluation(
    idea_id: str,
    current_user: Annotated[UserPublic, Depends(get_current_user)],
) -> dict[str, str]:
    """Re-trigger evaluation for an existing idea.

    Only allowed when the idea is in 'pending' or 'evaluated' status.
    Returns 409 if the idea is currently being evaluated.
    """
    store = get_store()
    emitter = get_event_emitter()
    data_dir = get_data_dir()

    idea = store.get_idea(idea_id)
    if idea is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Idea not found: {idea_id}",
        )

    if idea.status == "evaluating":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Idea is currently being evaluated",
        )

    # Reset to pending if needed
    if idea.status != "pending":
        store.update_idea_status(idea_id, "pending")

    # Launch evaluation as a background task
    async def _background_eval() -> None:
        try:
            from policy_factory.ideas.evaluator import evaluate_idea

            await evaluate_idea(idea_id, store, emitter, data_dir)
        except Exception:
            logger.exception(
                "Background re-evaluation failed for idea %s", idea_id
            )

    asyncio.create_task(_background_eval())

    return {"idea_id": idea_id, "status": "evaluation_started"}
