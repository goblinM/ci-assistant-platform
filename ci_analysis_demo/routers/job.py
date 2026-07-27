from fastapi import APIRouter

from ..schemas.job_schema import CreatePipelineRequest, PipelineResponse

router = APIRouter(prefix="/job", tags=["job"])


@router.post("/pipelines", response_model=PipelineResponse)
def create_pipeline(data: CreatePipelineRequest):
    return {
        "pipeline_id": 1,
        "status": "running"
    }


@router.get("/pipelines/{pipeline_id}", response_model=PipelineResponse)
def get_pipeline(pipeline_id: int):
    return {
        "pipeline_id": pipeline_id,
        "status": "running"
    }
