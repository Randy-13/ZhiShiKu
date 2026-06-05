import media_parser


def test_identify_media_platforms():
    assert media_parser.identify_platform("https://www.bilibili.com/video/BV1A7V36BEc9?t=25.8") == "bilibili"
    assert media_parser.identify_platform("https://v.douyin.com/zXGKv6QWCM4/") == "douyin"
    assert media_parser.identify_platform("https://channels.weixin.qq.com/foo") == "wechat_channels"


def test_resolve_bilibili_preserves_bv_and_start_without_ytdlp(monkeypatch):
    monkeypatch.setattr(media_parser, "ytdlp_dump_json", lambda url: None)
    resolved = media_parser.resolve_url("https://www.bilibili.com/video/BV1A7V36BEc9?t=25.8")

    assert resolved.platform == "bilibili"
    assert "BV1A7V36BEc9" in resolved.canonical_url
    assert resolved.metadata["start_seconds"] == "25.8"


def test_resolve_douyin_extracts_video_id_from_redirect(monkeypatch):
    monkeypatch.setattr(
        media_parser,
        "follow_redirect",
        lambda url: "https://www.iesdouyin.com/share/video/7645662793240815025/?from=web_code_link",
    )
    resolved = media_parser.resolve_url("https://v.douyin.com/zXGKv6QWCM4/")

    assert resolved.platform == "douyin"
    assert resolved.metadata["video_id"] == "7645662793240815025"
    assert resolved.status == "resolved"


def test_parse_srt_to_timestamped_transcript():
    raw = """1
00:00:01,000 --> 00:00:03,500
第一句话

2
00:00:04,000 --> 00:00:06,000
第二句话
"""

    transcript = media_parser.parse_subtitle(raw, ".srt")

    assert "[00:00:01 - 00:00:03] 第一句话" in transcript
    assert "[00:00:04 - 00:00:06] 第二句话" in transcript


def test_failed_subtitle_payload_is_ignored():
    assert media_parser.looks_like_failed_subtitle("Not Found")
    assert media_parser.looks_like_failed_subtitle("<html><body>404</body></html>")
    assert not media_parser.looks_like_failed_subtitle("1\n00:00:01,000 --> 00:00:02,000\nhello")


def test_transcript_is_converted_to_readable_article():
    transcript = "\n".join(
        [
            "[00:00:01 - 00:00:03] first sentence.",
            "[00:00:03 - 00:00:05] second sentence.",
        ]
    )

    article = media_parser.to_readable_transcript(transcript)

    assert "00:00" not in article
    assert "first sentence." in article
    assert "second sentence." in article


def test_douyin_detail_excludes_chapter_recommendations_from_subtitle():
    detail = {
        "video_text": [],
        "is_subtitled": 0,
        "recommend_chapter_info": {
            "recommend_chapter_list": [
                {"desc": "intro", "detail": "too short", "timestamp": 0},
            ]
        },
        "music": {
            "play_url": {
                "url_list": ["https://example.com/audio.mp3"],
            }
        },
    }

    assert media_parser.extract_douyin_platform_subtitle(detail) == ""
    assert media_parser.extract_douyin_audio_url(detail) == "https://example.com/audio.mp3"
