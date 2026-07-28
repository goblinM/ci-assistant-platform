from fastapi import Request


def get_retriever(request: Request):
    """获取 ``get_retriever`` 对应的数据。"""
    return request.app.state.retriever


def get_gitlab_client(request: Request):
    """获取 ``get_gitlab_client`` 对应的数据。"""
    return request.app.state.gitlab_client


def get_tools_executor(request: Request):
    """获取 ``get_tools_executor`` 对应的数据。"""
    return request.app.state.tools_executor