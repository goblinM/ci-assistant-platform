from enum import Enum


class ErrorType(str, Enum):
    dependency_missing = "dependency_missing"
    repo_auth_failed = "repo_auth_failed"
    test_collection_failed = "test_collection_failed"
    test_failed = "test_failed"
    syntax_error = "syntax_error"
    timeout = "timeout"
    permission_error = "permission_error"
    docker_build_failed = "docker_build_failed"
    image_pull_failed = "image_pull_failed"
    network_error = "network_error"
    resource_exhausted = "resource_exhausted"
    dependency_conflict = "dependency_conflict"
    env_config_error = "env_config_error"
    unknown = "unknown"
