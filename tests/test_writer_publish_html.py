from pathlib import Path

import writer_tools


def test_prepare_publish_html_converts_native_lists_to_wechat_safe_rows(tmp_path):
    workspace = tmp_path / "writer" / "sample"
    workspace.mkdir(parents=True)
    html_path = workspace / "formatted.html"
    html_path.write_text(
        """
        <section>
          <p>但2000万次只是一个总量。</p>
          <ul style="margin:18px 0;padding:14px 18px;border:1px solid #ddd1bf;border-radius:10px;background:#fffaf1;">
            <li>单车日均单量是多少？</li>
            <li><p>单次出行的客单价是多少？</p></li>
            <li>单车的运营成本——电费、维护、远程安全员分摊——是多少？</li>
            <li>单车的回本周期是多少？</li>
          </ul>
        </section>
        """,
        encoding="utf-8",
    )

    publish_path = writer_tools.prepare_html_for_publish(workspace, html_path)
    html = publish_path.read_text(encoding="utf-8")
    report = (workspace / "publish_ready_sanitize_report.json").read_text(encoding="utf-8")

    assert "<ul" not in html
    assert "<li" not in html
    assert 'data-fl-component="wechat_list"' in html
    assert html.count('data-fl-list-row="1"') == 4
    assert html.count("•") == 4
    assert "单车日均单量是多少？" in html
    assert "单次出行的客单价是多少？" in html
    assert '"normalized_lists": 1' in report
    assert '"normalized_list_items": 4' in report
