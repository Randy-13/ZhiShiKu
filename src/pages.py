from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from src.shared.frontend_app import react_app_response
from src.shared.navigation import replace_app_rail


ROOT = Path(__file__).resolve().parents[1]
router = APIRouter()


@router.get("/public-beta", response_class=HTMLResponse)
def public_beta_page() -> HTMLResponse:
    return _info_page(
        title="知识酷内测说明",
        lead="知识酷公网内测采用邀请制开放，目标是验证真实素材收集、知识沉淀、视角挖掘和创作工作流。",
        sections=[
            (
                "当前阶段",
                [
                    "内测账号需要邀请码注册，服务可能按功能灰度开放。",
                    "长任务、上传、模型调用和第三方平台能力会受额度与权限限制。",
                    "内测期间会优先修复数据安全、任务稳定性和工作流闭环问题。",
                ],
            ),
            (
                "使用边界",
                [
                    "请不要上传违法、侵权、涉密或无法授权处理的材料。",
                    "AI 生成结果需要用户自行核对事实、来源、数据和发布合规性。",
                    "B 站 Cookie、公众号发布等高风险能力默认仅展示脱敏状态或由管理员配置。",
                ],
            ),
        ],
    )


@router.get("/privacy", response_class=HTMLResponse)
def privacy_page() -> HTMLResponse:
    return _info_page(
        title="隐私说明",
        lead="知识酷只围绕工作台任务处理必要数据，并尽量把路径、密钥、Cookie 和运行细节从普通用户界面中移除。",
        sections=[
            (
                "会处理的数据",
                [
                    "账号信息：邮箱、用户名、邀请码使用状态和登录会话。",
                    "工作内容：用户上传或输入的文本、文件、媒体链接、生成的原文、知识、视角和创作项目。",
                    "运行信息：任务状态、额度计数、错误摘要和必要的审计日志。",
                ],
            ),
            (
                "敏感信息",
                [
                    "API Key、Cookie、发布 Token 等配置应只写入，不应在普通用户接口中明文读回。",
                    "服务端本地路径、命令参数和堆栈信息只用于管理员排查，不面向普通用户展示。",
                    "第三方模型或平台调用会按任务需要发送相关内容，用户应避免提交无权处理的数据。",
                ],
            ),
        ],
    )


@router.get("/data-retention", response_class=HTMLResponse)
def data_retention_page() -> HTMLResponse:
    return _info_page(
        title="数据保存说明",
        lead="知识酷会同时使用数据库记录和 Markdown 文件保存知识内容，公网内测版本按用户与 workspace 逐步隔离。",
        sections=[
            (
                "保存方式",
                [
                    "原文、重点、视角和创作内容以 Markdown 文件为准，并同步维护数据库索引。",
                    "上传文件、媒体、图片和运行产物会进入服务端运行存储目录，cloud 模式会按用户目录隔离。",
                    "任务记录会保留状态、错误摘要和必要事件，便于重试、排查和额度统计。",
                ],
            ),
            (
                "删除与保留",
                [
                    "用户删除知识内容时，应通过工作台或后端接口执行，避免直接改动运行目录。",
                    "内测期间可能保留必要日志用于安全审计和故障排查。",
                    "如需清理账号或工作区数据，应联系管理员执行确认后的删除流程。",
                ],
            ),
        ],
    )


@router.get("/settings", response_class=HTMLResponse)
def settings_page() -> HTMLResponse:
    return react_app_response()


@router.get("/collect/media", response_class=HTMLResponse)
def collect_media_page() -> HTMLResponse:
    return _static_page("media.html", active_section="collect")


@router.get("/create", response_class=HTMLResponse)
def create_page() -> HTMLResponse:
    return react_app_response()


@router.get("/collect", response_class=HTMLResponse)
@router.get("/learn", response_class=HTMLResponse)
@router.get("/mine", response_class=HTMLResponse)
def app_workspace_alias(request: Request) -> HTMLResponse:
    return react_app_response()


def _static_page(filename: str, active_section: str) -> HTMLResponse:
    page_html = (ROOT / "static" / filename).read_text(encoding="utf-8")
    return HTMLResponse(replace_app_rail(page_html, active_section))


def _info_page(title: str, lead: str, sections: list[tuple[str, list[str]]]) -> HTMLResponse:
    section_html = "\n".join(
        f"""
        <section>
          <h2>{heading}</h2>
          <ul>
            {"".join(f"<li>{item}</li>" for item in items)}
          </ul>
        </section>
        """
        for heading, items in sections
    )
    return HTMLResponse(
        f"""<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <meta name="description" content="{lead}" />
    <title>{title}</title>
    <style>
      :root {{
        color: #17211d;
        background: #f5f6f2;
        font-family: "Microsoft YaHei", "PingFang SC", Arial, sans-serif;
      }}
      body {{
        margin: 0;
      }}
      main {{
        width: min(760px, calc(100% - 32px));
        margin: 0 auto;
        padding: 48px 0;
      }}
      a {{
        color: #0b6b4f;
        font-weight: 700;
        text-decoration: none;
      }}
      .back-link {{
        display: inline-flex;
        margin-bottom: 24px;
      }}
      article {{
        border: 1px solid #d9dfd7;
        border-radius: 12px;
        background: #fff;
        box-shadow: 0 18px 42px rgba(23, 33, 29, 0.1);
        padding: 28px;
      }}
      h1 {{
        margin: 0 0 12px;
        font-size: 30px;
        line-height: 1.2;
      }}
      .lead {{
        margin: 0 0 26px;
        color: #5f6b65;
        line-height: 1.7;
      }}
      section + section {{
        margin-top: 24px;
        padding-top: 20px;
        border-top: 1px solid #e6ebe4;
      }}
      h2 {{
        margin: 0 0 10px;
        font-size: 18px;
      }}
      ul {{
        display: grid;
        gap: 8px;
        margin: 0;
        padding-left: 20px;
        color: #334039;
        line-height: 1.7;
      }}
      @media (max-width: 640px) {{
        main {{
          width: min(100% - 24px, 760px);
          padding: 24px 0;
        }}
        article {{
          padding: 20px;
        }}
        h1 {{
          font-size: 24px;
        }}
      }}
    </style>
  </head>
  <body>
    <main>
      <a class="back-link" href="/">返回知识酷</a>
      <article>
        <h1>{title}</h1>
        <p class="lead">{lead}</p>
        {section_html}
      </article>
    </main>
  </body>
</html>"""
    )
