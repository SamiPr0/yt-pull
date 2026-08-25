from pydantic import BaseModel


class ResolveRequest(BaseModel):
    urls: list[str]


class DownloadRequest(BaseModel):
    url: str
    quality: str | None = None
