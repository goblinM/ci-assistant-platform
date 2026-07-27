from fastapi import Request


def get_retriever(request: Request):
    return request.app.state.retriever


def get_gitlab_client(request: Request):
    return request.app.state.gitlab_client


def get_tools_executor(request: Request):
    return request.app.state.tools_executor