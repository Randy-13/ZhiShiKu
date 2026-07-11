import media_parser
import sys
import types


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


def test_douyin_scraper_detail_is_cached_and_exposes_video_url(monkeypatch, tmp_path):
    monkeypatch.setattr(media_parser.storage, "MEDIA_DIR", tmp_path / "media")

    class FakeScraper:
        async def hybrid_parsing(self, url):
            return {
                "status": "success",
                "type": "video",
                "platform": "douyin",
                "aweme_id": "7645662793240815025",
                "desc": "scraper title",
                "author": {"nickname": "author"},
                "music": {"play_url": {"url_list": ["https://example.com/music.mp3"]}},
                "video_data": {"nwm_video_url": "https://example.com/video.mp4"},
            }

    fake_module = types.SimpleNamespace(Scraper=FakeScraper)
    monkeypatch.setitem(sys.modules, "douyin_tiktok_scraper.scraper", fake_module)

    detail = media_parser.fetch_douyin_detail_with_scraper("https://www.douyin.com/video/7645662793240815025")

    assert detail["desc"] == "scraper title"
    assert media_parser.extract_douyin_audio_url(detail) == "https://example.com/music.mp3"
    cached = tmp_path / "media" / "douyin_detail" / "7645662793240815025.json"
    assert cached.exists()


def test_douyin_detail_url_downloads_then_transcribes(monkeypatch, tmp_path):
    monkeypatch.setattr(media_parser.storage, "MEDIA_DIR", tmp_path / "media")
    updates = {}
    monkeypatch.setattr(media_parser.storage, "storage_relative", lambda path: str(path.relative_to(tmp_path)))
    monkeypatch.setattr(media_parser.storage, "update_media_source", lambda media_id, **fields: updates.update(fields))

    downloaded = tmp_path / "media" / "douyin_audio" / "douyin_7.mp4"
    monkeypatch.setattr(media_parser, "download_douyin_audio", lambda item, url: downloaded)
    monkeypatch.setattr(media_parser, "transcribe_audio", lambda path: f"transcribed from {path.name}")

    detail = {
        "aweme_id": "7645662793240815025",
        "video": {"play_addr": {"url_list": ["https://example.com/video.mp4"]}},
    }
    media_parser.write_douyin_detail_cache("7645662793240815025", detail)

    transcript = media_parser.transcript_from_douyin(
        {
            "id": 7,
            "platform": "douyin",
            "source_url": "https://www.douyin.com/video/7645662793240815025",
            "canonical_url": "https://www.douyin.com/video/7645662793240815025",
            "title": "douyin clip",
        }
    )

    assert transcript == "transcribed from douyin_7.mp4"
    assert updates["transcript_kind"] == "asr"
    assert updates["transcript_path"].startswith("media")


def test_douyin_missing_sources_reports_actionable_error(monkeypatch):
    monkeypatch.setattr(media_parser.storage, "MEDIA_DIR", media_parser.Path("__missing_test_media__"))
    monkeypatch.setattr(media_parser, "douyin_detail_from_cache", lambda item: None)
    monkeypatch.setattr(media_parser, "fetch_douyin_detail_with_scraper", lambda url: (_ for _ in ()).throw(RuntimeError("sdk unavailable")))
    monkeypatch.setattr(media_parser, "fetch_douyin_detail_with_downloader_api", lambda video_id: (_ for _ in ()).throw(RuntimeError("api unavailable")))
    monkeypatch.setattr(media_parser, "download_douyin_media_with_cli", lambda item: (_ for _ in ()).throw(RuntimeError("config missing")))

    try:
        media_parser.transcript_from_douyin(
            {
                "id": 8,
                "platform": "douyin",
                "source_url": "https://www.douyin.com/video/7645662793240815025",
                "canonical_url": "https://www.douyin.com/video/7645662793240815025",
            }
        )
    except RuntimeError as exc:
        message = str(exc)
    else:
        raise AssertionError("expected RuntimeError")

    assert "抖音链接暂时没有提取到" in message
    assert "SDK解析失败" in message
    assert "下载器API解析失败" in message
    assert "下载器兜底失败" in message
    assert "ASR 设置" in message


def test_ytdlp_cookie_source_reuses_project_auth_file(monkeypatch, tmp_path):
    monkeypatch.delenv(media_parser.YTDLP_COOKIES_FILE_ENV, raising=False)
    monkeypatch.delenv(media_parser.YTDLP_COOKIES_FROM_BROWSER_ENV, raising=False)
    monkeypatch.setattr(media_parser.storage, "ROOT", tmp_path)
    monkeypatch.setattr(media_parser.storage, "STORAGE_ROOT", tmp_path / "runtime")
    cookie_file = tmp_path / "auth" / "bilibili.cookies.txt"
    cookie_file.parent.mkdir()
    cookie_file.write_text("# Netscape HTTP Cookie File\n", encoding="utf-8")

    assert media_parser.ytdlp_cookie_source() == str(cookie_file)
    state = media_parser.ytdlp_auth_state()
    assert state.mode == "file"
    assert state.exists


def test_bilibili_login_error_with_existing_cookies_asks_to_refresh_file(tmp_path):
    cookie_file = tmp_path / "bilibili.cookies.txt"
    cookie_file.write_text("# Netscape HTTP Cookie File\n", encoding="utf-8")
    state = media_parser.YtDlpAuthState("file", str(cookie_file), True, "test")

    message = media_parser.explain_bilibili_subtitle_error(
        "ERROR: [BiliBili] Subtitles are only available when logged in",
        state,
    )

    assert "configured cookies were not accepted" in message
    assert "tools/browser_state_to_netscape_cookies.py" in message
    assert "anonymously" not in message


def test_bilibili_login_error_without_cookies_points_to_old_converter():
    message = media_parser.explain_bilibili_subtitle_error(
        "ERROR: [BiliBili] Subtitles are only available when logged in",
        media_parser.YtDlpAuthState("none"),
    )

    assert "auth/bilibili.cookies.txt" in message
    assert "tools/browser_state_to_netscape_cookies.py" in message


def test_browser_cookie_env_overrides_default_cookie_file(monkeypatch, tmp_path):
    monkeypatch.delenv(media_parser.YTDLP_COOKIES_FILE_ENV, raising=False)
    monkeypatch.setenv(media_parser.YTDLP_COOKIES_FROM_BROWSER_ENV, "edge")
    monkeypatch.setattr(media_parser.storage, "ROOT", tmp_path)
    monkeypatch.setattr(media_parser.storage, "STORAGE_ROOT", tmp_path / "runtime")
    cookie_file = tmp_path / "auth" / "bilibili.cookies.txt"
    cookie_file.parent.mkdir()
    cookie_file.write_text("# Netscape HTTP Cookie File\n", encoding="utf-8")

    state = media_parser.ytdlp_auth_state()

    assert state.mode == "browser"
    assert media_parser.ytdlp_auth_args() == ["--cookies-from-browser", "edge"]


def test_write_transcript_uses_storage_relative_path(monkeypatch, tmp_path):
    storage_root = tmp_path / "runtime"
    monkeypatch.setattr(media_parser.storage, "STORAGE_ROOT", storage_root)
    monkeypatch.setattr(media_parser.storage, "MEDIA_DIR", storage_root / "media")
    updates = {}
    monkeypatch.setattr(media_parser.storage, "update_media_source", lambda media_id, **fields: updates.update(fields))

    path = media_parser.write_transcript({"id": 18, "title": "demo"}, "[00:00:01 - 00:00:02] hello", "platform_subtitle")

    assert path.exists()
    assert updates["transcript_path"].startswith("media")
    assert not updates["transcript_path"].startswith(str(tmp_path))
    assert updates["status"] == "transcribed"


def test_garbled_transcript_detection_keeps_readable_text():
    garbled = "�" * 20 + "hu" + "�" * 40 + "\n" + "�L�Cz�ʒ" * 20
    readable = "[00:00:01 - 00:00:03] 股市指标与AI芯片相关讨论 H100 B300 MACD KDJ"

    assert media_parser.looks_like_garbled_transcript(garbled)
    assert not media_parser.looks_like_garbled_transcript(readable)


def test_ensure_transcript_discards_garbled_cache_and_retranscribes(monkeypatch, tmp_path):
    media_dir = tmp_path / "media"
    media_dir.mkdir()
    video_path = media_dir / "clip.mp3"
    video_path.write_bytes(b"audio")
    transcript_path = media_dir / "clip.txt"
    transcript_path.write_text("�" * 120, encoding="utf-8")
    updates = []
    item = {
        "id": 42,
        "source_kind": "local_file",
        "platform": "local",
        "title": "clip",
        "file_path": "media/clip.mp3",
        "transcript_path": "media/clip.txt",
        "transcript_kind": "asr",
        "status": "ready",
    }

    monkeypatch.setattr(media_parser.storage, "ROOT", tmp_path)
    monkeypatch.setattr(media_parser.storage, "STORAGE_ROOT", tmp_path)
    monkeypatch.setattr(media_parser.storage, "MEDIA_DIR", media_dir)
    monkeypatch.setattr(media_parser.storage, "storage_relative", lambda path: str(path.relative_to(tmp_path)))

    def fake_update(media_id, **fields):
        updates.append(fields)
        item.update(fields)
        return dict(item)

    monkeypatch.setattr(media_parser.storage, "update_media_source", fake_update)
    monkeypatch.setattr(media_parser.storage, "get_media_source", lambda media_id: dict(item))
    monkeypatch.setattr(media_parser, "transcribe_audio", lambda path: "重新识别后的可读文本")

    transcript, kind = media_parser.ensure_transcript(dict(item))

    assert transcript == "重新识别后的可读文本"
    assert kind == "asr"
    assert updates[0]["transcript_path"] is None
    assert updates[-1]["transcript_kind"] == "asr"
    assert not media_parser.looks_like_garbled_transcript((tmp_path / updates[-1]["transcript_path"]).read_text(encoding="utf-8"))


def test_bilibili_cookie_status_validates_required_keys(monkeypatch, tmp_path):
    monkeypatch.delenv(media_parser.YTDLP_COOKIES_FROM_BROWSER_ENV, raising=False)
    cookie_file = tmp_path / "bilibili.cookies.txt"
    cookie_file.write_text(
        "\n".join(
            [
                "# Netscape HTTP Cookie File",
                ".bilibili.com\tTRUE\t/\tTRUE\t0\tSESSDATA\tsecret",
                ".bilibili.com\tTRUE\t/\tTRUE\t0\tDedeUserID\t123",
                ".bilibili.com\tTRUE\t/\tTRUE\t0\tbili_jct\tcsrf",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv(media_parser.YTDLP_COOKIES_FILE_ENV, str(cookie_file))

    status = media_parser.bilibili_cookie_status()

    assert status["ok"] is True
    assert status["missing"] == []
    assert status["cookie_count"] == 3


def test_bilibili_cookie_status_reports_missing_keys(monkeypatch, tmp_path):
    cookie_file = tmp_path / "bilibili.cookies.txt"
    cookie_file.write_text("# Netscape HTTP Cookie File\n.bilibili.com\tTRUE\t/\tTRUE\t0\tSESSDATA\tsecret\n", encoding="utf-8")
    monkeypatch.setenv(media_parser.YTDLP_COOKIES_FILE_ENV, str(cookie_file))
    monkeypatch.delenv(media_parser.YTDLP_COOKIES_FROM_BROWSER_ENV, raising=False)

    status = media_parser.bilibili_cookie_status()

    assert status["ok"] is False
    assert "DedeUserID" in status["missing"]
