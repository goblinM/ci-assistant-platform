from fastapi import APIRouter

from ..schemas.job_schema import CreatePipelineRequest, PipelineResponse

router = APIRouter(prefix="/job", tags=["job"])


@router.post("/pipelines", response_model=PipelineResponse)
def create_pipeline(data: CreatePipelineRequest):
    """创建 ``create_pipeline`` 对应的领域对象或结果。"""
    return {
        "pipeline_id": 1,
        "status": "running"
    }


@router.get("/pipelines/{pipeline_id}", response_model=PipelineResponse)
def get_pipeline(pipeline_id: int):
    """获取 ``get_pipeline`` 对应的数据。"""
    return {
        "pipeline_id": pipeline_id,
        "status": "running"
    }
