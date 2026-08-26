from pydantic import BaseModel


class ResolveRequest(BaseModel):
    urls: list[str]
    lang: str | None = None


class DownloadRequest(BaseModel):
    url: str
    quality: str | None = None
