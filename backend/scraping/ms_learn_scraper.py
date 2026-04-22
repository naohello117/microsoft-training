"""
Microsoft Learn のラーニングパスをスクレイピングするモジュール。

Playwright を使って動的レンダリング後のDOMを取得し、
不要なナビゲーション・広告・フィードバック要素を除去した
純粋な学習テキストのみを抽出する。
"""

import re
import uuid
import datetime
import logging
from typing import Any
from playwright.async_api import async_playwright, Page

logger = logging.getLogger(__name__)

_REMOVE_SELECTORS = [
    "header", "footer", "nav", ".nav-bar", ".sidebar", ".toc",
    "#ms--header", "#ms--footer", ".feedback-section", ".rating-section",
    ".action-container", ".unit-action-bar", '[data-bi-name="feedback"]',
    ".learn-banner", ".alert", "script", "style", "noscript",
]

_CONTENT_SELECTORS = [
    "div.content", "main#main", "article", "div[role='main']",
]


async def scrape_from_url(source_url: str, include_content: bool = False) -> list[dict[str, Any]]:
    """入力URLを判別し、含まれる全ラーニングパスをスクレイピングする。

    対応URL:
    - /training/courses/<id>  : コース配下の全ラーニングパスを抽出してスクレイピング
    - /training/paths/<slug>/ : 単体のラーニングパス

    include_content=False (デフォルト): 目次のみ取得（数十秒で完了）。
        ユニット本文は初回アクセス時に scrape_single_unit() で遅延取得する。
    include_content=True: 全ユニットの本文も一括取得（10分タイムアウトに注意）。
    """
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (compatible; MSLearnBot/1.0; educational-use)",
            locale="ja-JP",
        )
        page = await context.new_page()
        try:
            if "/training/courses/" in source_url:
                path_urls = await _extract_path_urls_from_course(page, source_url)
                logger.info("コースから %d 件のラーニングパスを検出", len(path_urls))
                if not path_urls:
                    raise RuntimeError("コースページ内にラーニングパスが見つかりませんでした")
            elif "/training/paths/" in source_url:
                path_urls = [source_url]
            else:
                raise ValueError(
                    "サポートされていないURL形式です。"
                    "/training/courses/... または /training/paths/... を指定してください"
                )

            results: list[dict[str, Any]] = []
            for idx, p_url in enumerate(path_urls, 1):
                logger.info("(%d/%d) ラーニングパス目次取得: %s", idx, len(path_urls), p_url)
                path_data = await _scrape_path_structure(page, p_url)
                if include_content:
                    for module in path_data["modules"]:
                        for unit in module["units"]:
                            unit["raw_content"] = await _scrape_unit_content(page, unit["url"])
                            await page.wait_for_timeout(800)
                            logger.info("  ユニット完了: %s", unit["title"])
                results.append(path_data)
            return results
        finally:
            await browser.close()


async def scrape_single_unit(unit_url: str) -> str:
    """単一ユニットの本文を取得（遅延スクレイピング用）。"""
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (compatible; MSLearnBot/1.0; educational-use)",
            locale="ja-JP",
        )
        page = await context.new_page()
        try:
            return await _scrape_unit_content(page, unit_url)
        finally:
            await browser.close()


async def _extract_path_urls_from_course(page: Page, course_url: str) -> list[str]:
    """コースページから /training/paths/ 配下のURL一覧を抽出。"""
    await page.goto(course_url, wait_until="domcontentloaded", timeout=30000)
    await page.wait_for_timeout(2000)

    hrefs: list[str] = await page.evaluate(r"""() => {
        const links = Array.from(document.querySelectorAll('a[href*="/training/paths/"]'));
        const urls = links
            .map(a => {
                try {
                    const u = new URL(a.href);
                    const m = u.pathname.match(/\/training\/paths\/([^/?#]+)/);
                    if (!m) return null;
                    return u.origin + '/ja-jp/training/paths/' + m[1] + '/';
                } catch { return null; }
            })
            .filter(x => x);
        const seen = new Set();
        const result = [];
        for (const u of urls) {
            if (!seen.has(u)) { seen.add(u); result.push(u); }
        }
        return result;
    }""")
    return hrefs


# 後方互換エイリアス
async def scrape_learning_path(path_url: str) -> dict[str, Any]:
    results = await scrape_from_url(path_url)
    return results[0] if results else {}


async def _scrape_path_structure(page: Page, url: str) -> dict[str, Any]:
    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
    await page.wait_for_timeout(2000)

    title = await page.title()
    title = re.sub(r"\s*[-|]\s*Microsoft Learn.*$", "", title).strip()
    path_id = _url_to_id(url)

    # モジュールスラッグを抽出してモジュールルートURLに正規化（ユニットURLを除外）
    module_slugs: list[str] = await page.evaluate(r"""() => {
        const links = Array.from(document.querySelectorAll('a[href*="/training/modules/"]'));
        const seen = new Set();
        const result = [];
        for (const link of links) {
            try {
                const u = new URL(link.href);
                const m = u.pathname.match(/\/training\/modules\/([^/?#]+)/);
                if (!m) continue;
                const slug = m[1];
                if (!seen.has(slug)) {
                    seen.add(slug);
                    result.push(slug);
                }
            } catch {}
        }
        return result;
    }""")

    modules = []
    for i, slug in enumerate(module_slugs):
        module_url = f"https://learn.microsoft.com/ja-jp/training/modules/{slug}/"
        module_id = f"{path_id}-mod-{i+1:03d}"
        module_info = await _scrape_module(page, module_url, module_id, path_id)
        modules.append({
            "id": module_id,
            "learning_path_id": path_id,
            "title": module_info["title"] or f"モジュール {i+1}",
            "url": module_url,
            "order": i + 1,
            "units": module_info["units"],
            "unit_count": len(module_info["units"]),
        })

    return {
        "id": path_id,
        "title": title,
        "url": url,
        "modules": modules,
        "created_at": _now(),
        "updated_at": _now(),
    }


async def _scrape_module(
    page: Page, module_url: str, module_id: str, path_id: str
) -> dict[str, Any]:
    """モジュールページからタイトルとユニット一覧を取得して返す。"""
    try:
        await page.goto(module_url, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(1500)
    except Exception as exc:
        logger.warning("モジュール取得失敗 %s: %s", module_url, exc)
        return {"title": "", "units": []}

    # モジュールタイトルを h1 または document.title から抽出
    module_title: str = await page.evaluate(r"""() => {
        const h1 = document.querySelector('h1');
        if (h1 && h1.innerText.trim()) return h1.innerText.trim();
        return (document.title || '').replace(/\s*[-|]\s*(Microsoft Learn|Training).*$/, '').trim();
    }""")

    # モジュールスラッグを抽出してユニットリンクを特定
    # ユニットURLは /training/modules/<slug>/<unit-name>/ の形式
    m = re.search(r"/training/modules/([^/?#]+)", module_url)
    module_slug = m.group(1) if m else ""

    unit_links: list[dict] = await page.evaluate(f"""() => {{
        const slug = '{module_slug}';
        const pattern = '/training/modules/' + slug + '/';
        return Array.from(document.querySelectorAll('a[href]'))
            .filter(a => {{
                const path = a.pathname || '';
                const hash = a.hash || '';
                // アンカーのみのリンク・モジュールルート自体を除外
                if (hash && !path.replace(pattern, '').match(/^[a-z0-9-]+\/?$/)) return false;
                return path.includes(pattern) && path.replace(pattern, '').replace(/\/?$/, '').length > 0;
            }})
            .map(a => ({{
                href: a.href,
                text: a.innerText.trim()
            }}));
    }}""")

    seen: set[str] = set()
    units = []
    j = 0
    for u in unit_links:
        # アンカー・クエリを除去してパスのみで正規化
        href = u["href"].split("#")[0].split("?")[0].rstrip("/") + "/"
        # スラッグ部分が英数字・ハイフンのみの正規ユニットURLかチェック
        slug_part = href.split(f"/training/modules/{module_slug}/")[-1].rstrip("/")
        if not slug_part or not re.match(r"^[a-z0-9][a-z0-9\-]*$", slug_part):
            continue
        if href in seen or not u["text"]:
            continue
        seen.add(href)
        units.append({
            "id": f"{module_id}-unit-{j+1:03d}",
            "module_id": module_id,
            "learning_path_id": path_id,
            "title": u["text"].split("\n")[0].strip() or f"ユニット {j+1}",
            "url": href,
            "order": j + 1,
            "raw_content": "",
            "summary_ja": "",
            "is_scraped": False,
            "scraped_at": None,
        })
        j += 1

    return {"title": module_title, "units": units}


async def _scrape_unit_content(page: Page, url: str) -> str:
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(1500)
    except Exception as exc:
        logger.warning("ユニット取得失敗 %s: %s", url, exc)
        return ""

    # 不要要素を削除（セレクタをarg経由で渡しクォート衝突を回避）
    await page.evaluate(
        """(selectors) => {
            selectors.forEach(sel => {
                document.querySelectorAll(sel).forEach(el => el.remove());
            });
        }""",
        _REMOVE_SELECTORS,
    )

    # コンテンツエリアからテキスト取得
    for selector in _CONTENT_SELECTORS:
        text: str = await page.evaluate(f"""() => {{
            const el = document.querySelector('{selector}');
            return el ? el.innerText : '';
        }}""")
        text = _clean_text(text)
        if len(text) > 100:
            return text

    # フォールバック
    text = await page.evaluate("() => document.body.innerText")
    return _clean_text(text)


def _clean_text(text: str) -> str:
    text = re.sub(r"\n{3,}", "\n\n", text)
    lines = [line.strip() for line in text.splitlines()]
    cleaned, prev_blank = [], False
    for line in lines:
        if not line:
            if not prev_blank:
                cleaned.append("")
            prev_blank = True
        else:
            cleaned.append(line)
            prev_blank = False
    return "\n".join(cleaned).strip()


def _url_to_id(url: str) -> str:
    m = re.search(r"/training/(?:paths|modules)/([^/?#]+)", url)
    return m.group(1) if m else uuid.uuid4().hex[:12]


def _now() -> str:
    return datetime.datetime.utcnow().isoformat() + "Z"
