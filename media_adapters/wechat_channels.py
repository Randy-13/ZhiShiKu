from __future__ import annotations

from media_parser import ResolvedMedia


def resolve_wechat_channels_url(url: str) -> ResolvedMedia:
    return ResolvedMedia(
        platform="wechat_channels",
        source_url=url,
        canonical_url=url,
        title="WeChat Channels link",
        status="needs_local_file",
        error_message="WeChat Channels direct link capture is not available in v1. Please upload a saved video or audio file.",
    )


__all__ = ["resolve_wechat_channels_url"]
