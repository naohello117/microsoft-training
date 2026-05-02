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
from urllib.parse import urljoin

import aiohttp
from bs4 import BeautifulSoup

# Playwright は本番 (Linux Consumption) では動かないため遅延 import
# import 失敗時にもアプリ全体が落ちないようにオプショナル扱いにする
try:
    from playwright.async_api import async_playwright, Page  # type: ignore
    _PLAYWRIGHT_AVAILABLE = True
except Exception:  # ImportError or runtime
    _PLAYWRIGHT_AVAILABLE = False
    Page = Any  # type: ignore

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


async def scrape_from_url(source_url: str, include_content: bool = False) -> dict[str, Any]:
    """入力URLを判別し、含まれる全ラーニングパスをスクレイピングする。

    対応URL:
    - /credentials/certifications/exams/<exam-id>/ : 認定試験ページ配下のコース・パスを再帰的に抽出
    - /credentials/certifications/<cert-slug>/     : 認定資格ページ → 関連する試験IDを抽出し対応する試験ページを走査
    - /training/courses/<id>                        : コース配下の全ラーニングパスを抽出してスクレイピング
    - /training/paths/<slug>/                       : 単体のラーニングパス

    include_content=False (デフォルト): 目次のみ取得（数十秒で完了）。
        ユニット本文は初回アクセス時に scrape_single_unit() で遅延取得する。
    include_content=True: 全ユニットの本文も一括取得（10分タイムアウトに注意）。

    Returns:
        {"paths": [...], "exam_id": str|None, "exam_name": str|None}
    """
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (compatible; MSLearnBot/1.0; educational-use)",
            locale="ja-JP",
        )
        page = await context.new_page()
        try:
            derived_exam_id: str | None = None
            derived_exam_name: str | None = None
            path_urls: list[str] = []

            if "/credentials/certifications/exams/" in source_url:
                m = re.search(r"/credentials/certifications/exams/([a-z0-9-]+)", source_url, re.IGNORECASE)
                if m:
                    derived_exam_id = m.group(1).lower()
                    derived_exam_name = derived_exam_id.upper()
                course_urls, direct_path_urls = await _extract_links_from_certification(page, source_url)
                logger.info(
                    "認定試験ページからコース %d 件 / パス %d 件を直接検出",
                    len(course_urls), len(direct_path_urls),
                )
                path_urls = list(direct_path_urls)
                for c_url in course_urls:
                    sub_paths = await _extract_path_urls_from_course(page, c_url)
                    logger.info("  コース %s から %d 件のパスを抽出", c_url, len(sub_paths))
                    path_urls.extend(sub_paths)

            elif "/credentials/certifications/" in source_url:
                # 認定資格ページ → 紐づく試験ID一覧を抽出 → 各試験ページ配下を走査
                exam_ids = await _extract_exam_ids_from_certification_page(page, source_url)
                logger.info("認定資格ページから試験ID %d 件を検出: %s", len(exam_ids), exam_ids)
                if not exam_ids:
                    raise RuntimeError("認定資格ページから試験IDを抽出できませんでした")
                derived_exam_id = exam_ids[0]
                derived_exam_name = derived_exam_id.upper()
                for eid in exam_ids:
                    exam_url = f"https://learn.microsoft.com/ja-jp/credentials/certifications/exams/{eid}/"
                    course_urls, direct_path_urls = await _extract_links_from_certification(page, exam_url)
                    logger.info(
                        "  試験 %s からコース %d 件 / パス %d 件を検出",
                        eid, len(course_urls), len(direct_path_urls),
                    )
                    path_urls.extend(direct_path_urls)
                    for c_url in course_urls:
                        sub_paths = await _extract_path_urls_from_course(page, c_url)
                        path_urls.extend(sub_paths)

            elif "/training/courses/" in source_url:
                m = re.search(r"/training/courses/([a-z0-9-]+)", source_url, re.IGNORECASE)
                if m:
                    course_id = m.group(1).lower()
                    exam_m = re.match(r"^([a-z]+-\d+)t\d+$", course_id)
                    if exam_m:
                        derived_exam_id = exam_m.group(1)
                        derived_exam_name = derived_exam_id.upper()
                path_urls = await _extract_path_urls_from_course(page, source_url)
                logger.info("コースから %d 件のラーニングパスを検出", len(path_urls))

            elif "/training/paths/" in source_url:
                path_urls = [source_url]

            else:
                raise ValueError(
                    "サポートされていないURL形式です。"
                    "/credentials/certifications/... / /training/courses/... / "
                    "/training/paths/... のいずれかを指定してください"
                )

            # 順序保持の重複排除
            seen_paths: set[str] = set()
            deduped: list[str] = []
            for u in path_urls:
                if u not in seen_paths:
                    seen_paths.add(u)
                    deduped.append(u)
            path_urls = deduped
            logger.info("合計 %d 件のラーニングパスを取得", len(path_urls))
            if not path_urls:
                raise RuntimeError("ラーニングパスを1件も抽出できませんでした")

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
            return {
                "paths": results,
                "exam_id": derived_exam_id,
                "exam_name": derived_exam_name,
            }
        finally:
            await browser.close()


async def scrape_single_unit_http(unit_url: str) -> str:
    """単一ユニット本文を HTTP + BeautifulSoup で取得（Playwright 非依存／本番 Linux Consumption 対応）。

    Microsoft Learn のユニットページは本文が初期 HTML にレンダリングされているため、
    ブラウザ起動なしで取得できる。Playwright を使わない分、起動コストが小さく
    Functions Consumption でも動作する。
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "ja",
        "Accept": "text/html,application/xhtml+xml",
    }
    timeout = aiohttp.ClientTimeout(total=30)
    async with aiohttp.ClientSession(headers=headers, timeout=timeout) as session:
        async with session.get(unit_url, allow_redirects=True) as resp:
            resp.raise_for_status()
            html = await resp.text()
    return _extract_unit_text_from_html(html, base_url=unit_url)


def _extract_unit_text_from_html(html: str, base_url: str) -> str:
    """HTML 文字列から不要要素を除き、リンクを Markdown 形式に書き換えてテキストを返す。

    Playwright 版 (_scrape_unit_content) と同じセマンティクスを BeautifulSoup で再現。
    """
    soup = BeautifulSoup(html, "html.parser")

    # 不要要素を除去
    for sel in _REMOVE_SELECTORS:
        for el in soup.select(sel):
            el.decompose()

    # リンクを [text](absolute_url) Markdown 形式に書き換え
    for a in soup.find_all("a", href=True):
        raw_href = a.get("href", "").strip()
        if not raw_href or raw_href.startswith("#"):
            continue
        # 相対 URL を絶対 URL に解決
        href = urljoin(base_url, raw_href)
        if not re.match(r"^https?://", href):
            continue
        text = a.get_text(strip=True)
        if not text or text == href:
            continue
        a.replace_with(f"[{text}]({href})")

    # コンテンツエリアからテキストを取得
    for selector in _CONTENT_SELECTORS:
        el = soup.select_one(selector)
        if el is None:
            continue
        text = _clean_text(el.get_text(separator="\n", strip=False))
        if len(text) > 100:
            return text

    # フォールバック: body 全体
    body = soup.select_one("body")
    text = _clean_text(body.get_text(separator="\n", strip=False)) if body else ""
    return text


async def scrape_single_unit(unit_url: str) -> str:
    """単一ユニットの本文を取得（遅延スクレイピング用・後方互換）。

    本関数は Playwright 経由。Linux Consumption では動かないので、
    本番ランタイムからは scrape_single_unit_http() を使うこと。
    """
    if not _PLAYWRIGHT_AVAILABLE:
        # 本番環境などで Playwright が未インストールの場合は HTTP 版にフォールバック
        return await scrape_single_unit_http(unit_url)
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


async def _extract_links_from_certification(page: Page, cert_url: str) -> tuple[list[str], list[str]]:
    """認定試験ページからコースURLとラーニングパスURLを抽出して返す。

    返り値: (course_urls, path_urls)
    """
    await page.goto(cert_url, wait_until="domcontentloaded", timeout=30000)
    await page.wait_for_timeout(2000)

    extracted: dict[str, list[str]] = await page.evaluate(r"""() => {
        const courseUrls = new Set();
        const pathUrls = new Set();
        document.querySelectorAll('a[href]').forEach(a => {
            try {
                const u = new URL(a.href);
                let m;
                if (m = u.pathname.match(/\/training\/courses\/([^/?#]+)/)) {
                    courseUrls.add(u.origin + '/ja-jp/training/courses/' + m[1] + '/');
                } else if (m = u.pathname.match(/\/training\/paths\/([^/?#]+)/)) {
                    pathUrls.add(u.origin + '/ja-jp/training/paths/' + m[1] + '/');
                }
            } catch {}
        });
        return { courses: [...courseUrls], paths: [...pathUrls] };
    }""")
    return extracted["courses"], extracted["paths"]


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


async def _extract_exam_ids_from_certification_page(page: Page, cert_url: str) -> list[str]:
    """認定資格ページ（/credentials/certifications/<cert-slug>/）から紐づく試験IDを抽出する。

    抽出ソース（優先順）:
    1. `/credentials/certifications/exams/<id>/` 形式のリンク
    2. ページHTML内の `exam.XX-NNN` パターン（Pearson Vue スケジューリングURL等）
    """
    await page.goto(cert_url, wait_until="domcontentloaded", timeout=30000)
    await page.wait_for_timeout(2000)

    ids: list[str] = await page.evaluate(r"""() => {
        const found = new Set();
        // リンクから /credentials/certifications/exams/<id>/
        document.querySelectorAll('a[href]').forEach(a => {
            try {
                const u = new URL(a.href);
                const m = u.pathname.match(/\/credentials\/certifications\/exams\/([a-z0-9-]+)/i);
                if (m) found.add(m[1].toLowerCase());
            } catch {}
        });
        // ページHTML全体から exam.XX-NNN パターン（ハイフン区切りの短いコード）
        const html = document.documentElement.outerHTML;
        const re = /exam\.([a-z]+-\d+)/gi;
        let m;
        while ((m = re.exec(html)) !== null) {
            found.add(m[1].toLowerCase());
        }
        return [...found];
    }""")
    # 安定した順序にするためアルファベット順で返す
    return sorted(ids)


# 後方互換エイリアス
async def scrape_learning_path(path_url: str) -> dict[str, Any]:
    result = await scrape_from_url(path_url)
    paths = result.get("paths", [])
    return paths[0] if paths else {}


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

    # innerText が <a href> の URL を捨てるため、事前に [text](url) 形式に書き換える
    await page.evaluate(
        """() => {
            document.querySelectorAll('a[href]').forEach(a => {
                const rawHref = a.getAttribute('href') || '';
                if (rawHref.startsWith('#')) return;            // 同一ページ内アンカーは無視
                const href = a.href;                            // ブラウザが絶対URLに解決
                if (!href || !/^https?:/i.test(href)) return;   // javascript: 等を除外
                const text = (a.innerText || '').trim();
                if (!text) return;
                if (text === href) return;                      // テキストとURLが同一なら不要
                a.textContent = `[${text}](${href})`;
            });
        }"""
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
