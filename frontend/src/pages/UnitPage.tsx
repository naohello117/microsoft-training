import { useEffect, useState, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import { api, Unit, Quiz } from "../api/client";
import { useAuth } from "../auth";

const USER_ID = "demo-user"; // Static Web Apps の認証ヘッダーから取得するよう後で差し替え

// Markdown 内リンクを日本語ドキュメントに差し替え、別タブで開く
function toJaLocaleHref(href: string | undefined): string | undefined {
  if (!href) return href;
  return href
    .replace(/^(https?:\/\/[^/]*learn\.microsoft\.com)\/en-us\//i, "$1/ja-jp/")
    .replace(/^(https?:\/\/[^/]*microsoft\.com)\/en-us\//i, "$1/ja-jp/");
}

const MARKDOWN_COMPONENTS = {
  a: ({ href, children, ...rest }: React.AnchorHTMLAttributes<HTMLAnchorElement>) => (
    <a
      {...rest}
      href={toJaLocaleHref(href)}
      target="_blank"
      rel="noopener noreferrer"
    >
      {children}
    </a>
  ),
};

// 時間経過に応じて進捗メッセージを切り替える
function pickStep(elapsedMs: number, steps: { untilSec: number; label: string }[]): string {
  const elapsedSec = elapsedMs / 1000;
  for (const s of steps) {
    if (elapsedSec < s.untilSec) return s.label;
  }
  return steps[steps.length - 1].label;
}

const SUMMARY_STEPS = [
  { untilSec: 6, label: "① ユニット本文を取得しています…" },
  { untilSec: 25, label: "② AIエージェントが日本語要約を生成しています…" },
  { untilSec: 60, label: "③ もう少しで完了します…" },
  { untilSec: Infinity, label: "④ まだ処理中です。通常は60秒以内に完了します…" },
];

const QUIZ_STEPS = [
  { untilSec: 5, label: "① 学習コンテンツを読み込んでいます…" },
  { untilSec: 25, label: "② AIエージェントがクイズを作成しています…" },
  { untilSec: 60, label: "③ 最終調整中…" },
  { untilSec: Infinity, label: "④ まだ処理中です。通常は60秒以内に完了します…" },
];

// 進捗インジケータ
function ProgressIndicator(props: { startedAt: number; steps: { untilSec: number; label: string }[]; title: string }) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 250);
    return () => clearInterval(id);
  }, []);
  const elapsedMs = now - props.startedAt;
  const elapsedSec = (elapsedMs / 1000).toFixed(1);
  const label = pickStep(elapsedMs, props.steps);
  return (
    <div
      style={{
        background: "#eef6ff",
        border: "1px solid #cfe3ff",
        padding: "0.9rem 1.1rem",
        borderRadius: 6,
        margin: "0.5rem 0 1rem",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: "0.6rem" }}>
        <span className="_spinner" aria-hidden />
        <strong style={{ color: "#0352a6" }}>{props.title}</strong>
        <span style={{ color: "#666", fontSize: "0.85em", marginLeft: "auto" }}>{elapsedSec}秒経過</span>
      </div>
      <p style={{ margin: "0.4rem 0 0", color: "#333", fontSize: "0.95em" }}>{label}</p>
      <style>{`
        ._spinner {
          width: 14px; height: 14px; border-radius: 50%;
          border: 2px solid #cfe3ff; border-top-color: #0078d4;
          display: inline-block; animation: _spin 0.9s linear infinite;
        }
        @keyframes _spin { to { transform: rotate(360deg); } }
      `}</style>
    </div>
  );
}

export default function UnitPage() {
  const { unitId = "" } = useParams<{ unitId: string }>();
  const navigate = useNavigate();
  const { isAdmin } = useAuth();
  const [unit, setUnit] = useState<Unit | null>(null);
  const [quizzes, setQuizzes] = useState<Quiz[]>([]);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [showResults, setShowResults] = useState(false);
  const [unitLoading, setUnitLoading] = useState(true);
  const [summaryStartedAt, setSummaryStartedAt] = useState<number | null>(null);
  const [quizLoading, setQuizLoading] = useState(false);
  const [quizStartedAt, setQuizStartedAt] = useState<number | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [nextUnitId, setNextUnitId] = useState<string | null>(null);
  const [nextUnitTitle, setNextUnitTitle] = useState<string | null>(null);
  const lastFetchedId = useRef<string | null>(null);

  // 要約生成 + SWA 45 秒タイムアウト対策のポーリング。
  // POST /api/summarize は SWA で 45 秒で切断されることがあるが、
  // Function App 側はそのまま走り続けて Cosmos に要約を保存する。
  // よって失敗時は GET /api/content をポーリングして summary_ja の出現を待つ。
  async function generateSummaryWithFallback(force = false): Promise<Unit> {
    try {
      return await api.summarizeUnit(unitId, force);
    } catch (err) {
      // POST がタイムアウト/エラー → 5秒間隔で最大 24 回 (約2分) ポーリング
      for (let i = 0; i < 24; i++) {
        await new Promise((r) => setTimeout(r, 5000));
        try {
          const u = await api.getContent(unitId);
          if (u.summary_ja) return u;
        } catch {
          /* 一時エラーは無視して継続 */
        }
      }
      throw err;
    }
  }

  // unitId が変わったら（次へクリックなどで URL 遷移したら）状態をリセットして再ロード
  useEffect(() => {
    if (lastFetchedId.current === unitId) return;
    lastFetchedId.current = unitId;

    // 状態リセット
    setUnit(null);
    setQuizzes([]);
    setAnswers({});
    setShowResults(false);
    setErrorMsg(null);
    setNextUnitId(null);
    setNextUnitTitle(null);
    setUnitLoading(true);
    setSummaryStartedAt(Date.now());
    // ページ遷移時はトップに戻る
    window.scrollTo({ top: 0, behavior: "auto" });

    (async () => {
      try {
        // 段階1: 本文取得（必要なら遅延スクレイピング）。Foundry を呼ばないので速い
        const u = await api.getContent(unitId);
        setUnit(u);
        setUnitLoading(false);
        // 段階2: 要約が未生成なら Foundry 呼び出し（バックグラウンドポーリングで完結）
        if (!u.summary_ja) {
          const summarized = await generateSummaryWithFallback();
          setUnit(summarized);
        }
      } catch (err) {
        setErrorMsg(err instanceof Error ? err.message : String(err));
      } finally {
        setUnitLoading(false);
        setSummaryStartedAt(null);
      }
    })();
  }, [unitId]);

  // unit がロードされたら次のユニットを解決（同モジュール内 → モジュール終端なら次モジュール先頭）
  useEffect(() => {
    if (!unit?.id || !unit.module_id) return;
    let cancelled = false;
    (async () => {
      try {
        const siblings = await api.getModuleUnits(unit.module_id);
        const sorted = [...siblings].sort((a, b) => a.order - b.order);
        const idx = sorted.findIndex((u) => u.id === unit.id);
        if (idx >= 0 && idx < sorted.length - 1) {
          if (cancelled) return;
          setNextUnitId(sorted[idx + 1].id);
          setNextUnitTitle(sorted[idx + 1].title);
          return;
        }
        // モジュール末尾なので次モジュールの先頭ユニットを探す
        if (!unit.learning_path_id) return;
        const paths = await api.listLearningPaths();
        const path = paths.find((p) => p.id === unit.learning_path_id);
        if (!path?.modules) return;
        const sortedMods = [...path.modules].sort((a, b) => a.order - b.order);
        const modIdx = sortedMods.findIndex((m) => m.id === unit.module_id);
        if (modIdx < 0 || modIdx >= sortedMods.length - 1) return;
        const nextMod = sortedMods[modIdx + 1];
        const nextUnits = await api.getModuleUnits(nextMod.id);
        const sortedNext = [...nextUnits].sort((a, b) => a.order - b.order);
        if (cancelled) return;
        if (sortedNext.length > 0) {
          setNextUnitId(sortedNext[0].id);
          setNextUnitTitle(sortedNext[0].title);
        }
      } catch {
        /* 解決できなければ次へボタンは表示しない */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [unit?.id, unit?.module_id, unit?.learning_path_id]);

  function goNext() {
    if (nextUnitId) navigate(`/unit/${nextUnitId}`);
  }

  async function handleRegenerateSummary() {
    setErrorMsg(null);
    setUnit((u) => (u ? { ...u, summary_ja: "" } : u));
    setSummaryStartedAt(Date.now());
    try {
      const u = await generateSummaryWithFallback(true);
      setUnit(u);
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : String(err));
    } finally {
      setSummaryStartedAt(null);
    }
  }

  // クイズ生成 + SWA 45 秒切断対策のポーリング (要約と同じパターン)
  async function generateQuizWithFallback(): Promise<Quiz[]> {
    try {
      return await api.generateQuiz(unitId);
    } catch (err) {
      // POST がタイムアウト/エラー → 5秒間隔で最大 24 回 (約2分) ポーリング
      for (let i = 0; i < 24; i++) {
        await new Promise((r) => setTimeout(r, 5000));
        try {
          const qs = await api.listQuizzes(unitId);
          if (qs.length > 0) return qs;
        } catch {
          /* 一時エラーは無視して継続 */
        }
      }
      throw err;
    }
  }

  async function handleLoadQuiz() {
    setErrorMsg(null);
    setQuizLoading(true);
    setQuizStartedAt(Date.now());
    try {
      const qs = await generateQuizWithFallback();
      setQuizzes(qs);
      setAnswers({});
      setShowResults(false);
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : String(err));
    } finally {
      setQuizLoading(false);
      setQuizStartedAt(null);
    }
  }

  async function handleSubmit() {
    setShowResults(true);
    for (const q of quizzes) {
      const answered = answers[q.id];
      if (!answered) continue;
      await api.saveProgress(USER_ID, {
        unit_id: unitId,
        quiz_result: {
          quiz_id: q.id,
          answered_key: answered,
          is_correct: answered === q.correct_key,
        },
      });
    }
  }

  if (unitLoading && !unit) {
    return (
      <div style={{ maxWidth: 800, margin: "0 auto", padding: "2rem" }}>
        <button
          style={{ background: "none", border: "none", color: "#0078d4", cursor: "pointer", fontSize: "0.9rem", padding: 0, marginBottom: "1rem" }}
          onClick={() => navigate(-1)}
        >
          ← 戻る
        </button>
        {summaryStartedAt !== null && (
          <ProgressIndicator
            title="ユニットを読み込んでいます"
            startedAt={summaryStartedAt}
            steps={SUMMARY_STEPS}
          />
        )}
        {errorMsg && <p style={{ color: "#c00" }}>エラー: {errorMsg}</p>}
      </div>
    );
  }
  if (!unit) {
    // 503 content_not_cached の場合はバックエンドが構造化エラーを返している
    let friendly: string | null = null;
    let isNotCached = false;
    if (errorMsg) {
      const m = errorMsg.match(/\{.*\}/);
      if (m) {
        try {
          const parsed = JSON.parse(m[0]);
          if (parsed?.error === "content_not_cached") {
            isNotCached = true;
            friendly = parsed.message;
          } else if (parsed?.message) {
            friendly = parsed.message;
          }
        } catch {
          /* fall through */
        }
      }
    }
    return (
      <div style={{ maxWidth: 800, margin: "0 auto", padding: "2rem" }}>
        <button
          style={{ background: "none", border: "none", color: "#0078d4", cursor: "pointer", fontSize: "0.9rem", padding: 0, marginBottom: "1rem" }}
          onClick={() => navigate(-1)}
        >
          ← 戻る
        </button>
        {isNotCached ? (
          <div style={{ background: "#fff3cd", border: "1px solid #ffeeba", color: "#856404", padding: "1rem 1.25rem", borderRadius: 6 }}>
            <strong>このユニットの本文はまだ取得されていません</strong>
            <p style={{ margin: "0.5rem 0 0" }}>{friendly}</p>
            <p style={{ margin: "0.5rem 0 0", fontSize: "0.85rem" }}>
              管理者はローカル環境（<code>npm run dev</code> + <code>func start</code>）でこのユニットを開いてください。本文取得 → 要約生成 → 本番 Cosmos に保存されると、本番 SWA でも表示できるようになります。詳細は <code>HowToUse.md</code> を参照。
            </p>
          </div>
        ) : (
          <p style={{ color: "#c00" }}>
            {friendly ?? errorMsg ?? "ユニットが見つかりません"}
          </p>
        )}
      </div>
    );
  }

  const score = showResults
    ? quizzes.filter((q) => answers[q.id] === q.correct_key).length
    : null;

  return (
    <div style={{ maxWidth: 800, margin: "0 auto", padding: "2rem" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
        <button
          style={{ background: "none", border: "none", color: "#0078d4", cursor: "pointer", fontSize: "0.9rem", padding: 0 }}
          onClick={() => navigate(-1)}
        >
          ← 戻る
        </button>
        {nextUnitId && (
          <button
            style={{ background: "none", border: "none", color: "#0078d4", cursor: "pointer", fontSize: "0.9rem", padding: 0 }}
            onClick={goNext}
            title={nextUnitTitle ?? undefined}
          >
            次のユニット →
          </button>
        )}
      </div>
      <h2>{unit.title}</h2>

      {errorMsg && (
        <p style={{ background: "#f8d7da", color: "#842029", padding: "0.6rem 0.9rem", borderRadius: 4 }}>
          エラー: {errorMsg}
        </p>
      )}

      {unit.summary_ja ? (
        <section>
          <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "0.25rem" }}>
            <h3 style={{ margin: 0 }}>要約</h3>
            {isAdmin && (
              <button
                onClick={handleRegenerateSummary}
                disabled={summaryStartedAt !== null}
                style={{
                  background: "none",
                  border: "1px solid #0078d4",
                  color: "#0078d4",
                  padding: "0.2rem 0.6rem",
                  borderRadius: 4,
                  fontSize: "0.8rem",
                  cursor: summaryStartedAt !== null ? "not-allowed" : "pointer",
                }}
                title="summary-agent で要約を再生成します"
              >
                ↻ 再要約
              </button>
            )}
          </div>
          <div style={{ background: "#f8f9fa", padding: "1rem 1.25rem", borderRadius: 4, lineHeight: 1.7 }}>
            <ReactMarkdown components={MARKDOWN_COMPONENTS}>{unit.summary_ja}</ReactMarkdown>
          </div>
        </section>
      ) : (
        summaryStartedAt !== null && (
          <ProgressIndicator
            title="要約を生成中"
            startedAt={summaryStartedAt}
            steps={SUMMARY_STEPS}
          />
        )
      )}

      <hr />

      <section>
        <h3>習熟度チェック</h3>
        {quizLoading && quizStartedAt !== null ? (
          <ProgressIndicator
            title="クイズを生成中"
            startedAt={quizStartedAt}
            steps={QUIZ_STEPS}
          />
        ) : quizzes.length === 0 ? (
          <button onClick={handleLoadQuiz} style={{ padding: "0.5rem 1rem" }}>
            クイズを生成する
          </button>
        ) : (
          <>
            {quizzes.map((q, i) => (
              <div key={q.id} style={{ marginBottom: "1.5rem" }}>
                <p><strong>Q{i + 1}. {q.question}</strong></p>
                {q.choices.map((c) => {
                  const selected = answers[q.id] === c.key;
                  const correct = showResults && c.key === q.correct_key;
                  const wrong = showResults && selected && c.key !== q.correct_key;
                  return (
                    <label
                      key={c.key}
                      style={{
                        display: "block",
                        padding: "0.3rem 0.5rem",
                        background: correct ? "#d4edda" : wrong ? "#f8d7da" : "transparent",
                        borderRadius: 4,
                        cursor: showResults ? "default" : "pointer",
                      }}
                    >
                      <input
                        type="radio"
                        name={q.id}
                        value={c.key}
                        checked={selected}
                        disabled={showResults}
                        onChange={() => setAnswers((a) => ({ ...a, [q.id]: c.key }))}
                      />
                      {" "}{c.key}. {c.text}
                    </label>
                  );
                })}
                {showResults && (
                  <p style={{ marginTop: "0.5rem", color: "#555", fontSize: "0.9em" }}>
                    解説: {q.explanation}
                  </p>
                )}
              </div>
            ))}

            {!showResults ? (
              <button
                onClick={handleSubmit}
                disabled={Object.keys(answers).length < quizzes.length}
                style={{ padding: "0.5rem 1rem" }}
              >
                回答を確認する
              </button>
            ) : (
              <p style={{ fontWeight: "bold" }}>
                結果: {score} / {quizzes.length} 問正解
              </p>
            )}
          </>
        )}
      </section>

      {/* 学習完了後のナビゲーション。次のユニットがあればそちらへ、無ければラーニングパス完了の表示 */}
      <hr style={{ marginTop: "2.5rem" }} />
      <nav style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: "1.5rem", gap: "1rem" }}>
        <button
          onClick={() => navigate(-1)}
          style={{
            padding: "0.6rem 1.2rem",
            background: "#f6f8fa",
            border: "1px solid #d0d7de",
            borderRadius: 6,
            cursor: "pointer",
            fontSize: "0.95rem",
            color: "#24292f",
          }}
        >
          ← 一覧へ戻る
        </button>
        {nextUnitId ? (
          <button
            onClick={goNext}
            style={{
              padding: "0.6rem 1.4rem",
              background: "#0078d4",
              color: "#fff",
              border: "none",
              borderRadius: 6,
              cursor: "pointer",
              fontSize: "0.95rem",
              fontWeight: 500,
              maxWidth: "60%",
              textAlign: "right",
            }}
            title={nextUnitTitle ?? undefined}
          >
            次のユニット: {nextUnitTitle ? (nextUnitTitle.length > 24 ? nextUnitTitle.slice(0, 22) + "…" : nextUnitTitle) : ""} →
          </button>
        ) : (
          <span style={{ color: "#666", fontSize: "0.9rem" }}>
            🎉 ラーニングパスの最終ユニットです
          </span>
        )}
      </nav>
    </div>
  );
}
