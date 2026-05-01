import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { api, Exam } from "../api/client";
import { useAuth } from "../auth";

const EXAM_META: Record<string, { color: string; desc: string }> = {
  "az-500": { color: "#0078d4", desc: "Microsoft Azure Security Technologies" },
  "sc-300": { color: "#107c41", desc: "Microsoft Identity and Access Administrator" },
  "sc-100": { color: "#8764b8", desc: "Microsoft Cybersecurity Architect" },
};

const FALLBACK_COLORS = [
  "#d83b01", "#5c2d91", "#038387", "#881798", "#c239b3", "#107c10", "#004e8c", "#8e562e",
];

function colorForExam(examId: string): string {
  if (EXAM_META[examId]) return EXAM_META[examId].color;
  let h = 0;
  for (let i = 0; i < examId.length; i++) h = (h * 31 + examId.charCodeAt(i)) | 0;
  return FALLBACK_COLORS[Math.abs(h) % FALLBACK_COLORS.length];
}

// 簡易的な URL バリデーション（Microsoft Learn 配下か）
function isSupportedUrl(url: string): boolean {
  return /^https?:\/\/[^/]*learn\.microsoft\.com\//i.test(url);
}

const s = {
  page: { maxWidth: 900, margin: "0 auto", padding: "2rem", fontFamily: "sans-serif" } as const,
  form: { display: "flex", gap: "0.5rem", marginTop: "1rem", marginBottom: "0.4rem" } as const,
  input: {
    flex: 1,
    padding: "0.5rem 0.75rem",
    fontSize: "0.9rem",
    border: "1px solid #ccc",
    borderRadius: 4,
  } as const,
  btn: {
    padding: "0.5rem 1rem",
    background: "#0078d4",
    color: "#fff",
    border: "none",
    borderRadius: 4,
    cursor: "pointer",
    fontSize: "0.9rem",
  } as const,
  hint: { fontSize: "0.8rem", color: "#888", margin: "0 0 1rem" } as const,
  status: (ok: boolean) => ({
    padding: "0.75rem",
    borderRadius: 4,
    background: ok ? "#d4edda" : "#f8d7da",
    color: ok ? "#155724" : "#842029",
    marginBottom: "1rem",
  } as const),
  progress: {
    background: "#eef6ff",
    border: "1px solid #cfe3ff",
    padding: "0.9rem 1.1rem",
    borderRadius: 6,
    margin: "0.5rem 0 1rem",
  } as const,
  grid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))",
    gap: "1rem",
    marginTop: "1.5rem",
  } as const,
  card: (color: string) => ({
    border: `2px solid ${color}`,
    borderRadius: 8,
    padding: "1.5rem",
    cursor: "pointer",
    transition: "box-shadow 0.15s",
    background: "#fff",
  } as const),
  examId: (color: string) => ({
    display: "inline-block",
    background: color,
    color: "#fff",
    fontWeight: "bold",
    fontSize: "1.1rem",
    padding: "0.2rem 0.6rem",
    borderRadius: 4,
    marginBottom: "0.5rem",
  } as const),
  desc: { color: "#555", fontSize: "0.9rem", marginBottom: "0.75rem" } as const,
  count: { fontSize: "0.8rem", color: "#888" } as const,
};

export default function ExamListPage() {
  const navigate = useNavigate();
  const { isAdmin } = useAuth();
  const [exams, setExams] = useState<Exam[]>([]);
  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [startedAt, setStartedAt] = useState<number | null>(null);
  const [now, setNow] = useState(Date.now());
  const [msg, setMsg] = useState<{ text: string; ok: boolean } | null>(null);

  async function loadExams() {
    try {
      const res = await api.listExams();
      setExams(res);
    } catch {
      setExams([]);
    }
  }

  useEffect(() => {
    loadExams();
  }, []);

  useEffect(() => {
    if (!loading) return;
    const id = setInterval(() => setNow(Date.now()), 250);
    return () => clearInterval(id);
  }, [loading]);

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = url.trim();
    if (!isSupportedUrl(trimmed)) {
      setMsg({
        text: "Microsoft Learn (learn.microsoft.com) のURLを指定してください。",
        ok: false,
      });
      return;
    }
    setLoading(true);
    setStartedAt(Date.now());
    setMsg(null);
    try {
      // 試験IDはバックエンド側で自動判別 — フロントからは明示指定しない
      const res = await api.scrapeUrl(trimmed);
      const examLabel = res.exam_name || res.exam_id || "未分類";
      setMsg({
        text: `${examLabel} に ${res.paths.length} 件のラーニングパスを追加しました`,
        ok: true,
      });
      setUrl("");
      await loadExams();
    } catch (err) {
      setMsg({
        text: `エラー: ${err instanceof Error ? err.message : String(err)}`,
        ok: false,
      });
    } finally {
      setLoading(false);
      setStartedAt(null);
    }
  }

  // API から返ってきた（= 実際にコンテンツが投入されている）試験のみ表示
  // 既知 ID を優先してソートし、未知 ID は exam_id 昇順
  const knownOrder = ["az-500", "sc-300", "sc-100"];
  const displayExams = [...exams].sort((a, b) => {
    const ai = knownOrder.indexOf(a.exam_id);
    const bi = knownOrder.indexOf(b.exam_id);
    if (ai !== -1 && bi !== -1) return ai - bi;
    if (ai !== -1) return -1;
    if (bi !== -1) return 1;
    return a.exam_id.localeCompare(b.exam_id);
  });

  const elapsedSec = startedAt ? ((now - startedAt) / 1000).toFixed(1) : "0.0";

  return (
    <div style={s.page}>
      <h2 style={{ marginBottom: "0.25rem" }}>試験コレクション</h2>
      <p style={{ color: "#666", marginTop: 0 }}>
        {isAdmin
          ? "学習したい試験を選択、または新しい試験URLを追加してください"
          : "学習したい試験を選択してください"}
      </p>

      {isAdmin && (
        <>
          <form onSubmit={handleAdd} style={s.form}>
            <input
              style={s.input}
              type="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="Microsoft Learn のURL（認定資格ページ / 認定試験ページ / コース / ラーニングパス のいずれでも可）"
              required
              disabled={loading}
            />
            <button type="submit" style={s.btn} disabled={loading}>
              {loading ? "取得中..." : "試験を追加"}
            </button>
          </form>
          <p style={s.hint}>
            試験IDはサーバー側で自動判別します（認定資格ページ / 認定試験ページ / コース / パス URL に対応）。判別できない場合は「未分類」に分類されます。
          </p>
        </>
      )}

      {loading && startedAt !== null && (
        <div style={s.progress}>
          <strong style={{ color: "#0352a6" }}>ラーニングパスをスクレイピング中…</strong>
          <span style={{ color: "#666", fontSize: "0.85em", marginLeft: "0.8rem" }}>
            {elapsedSec}秒経過
          </span>
          <p style={{ margin: "0.4rem 0 0", color: "#333", fontSize: "0.9em" }}>
            試験ページ解析 → 配下のコース/パスを抽出 → 各パスの目次を取得しています。
            ラーニングパス数が多いと数分かかる場合があります。
          </p>
        </div>
      )}

      {msg && <p style={s.status(msg.ok)}>{msg.text}</p>}

      {displayExams.length === 0 && !loading && (
        <div style={{ marginTop: "2rem", padding: "1.5rem", border: "1px dashed #ccc", borderRadius: 6, color: "#555", textAlign: "center" }}>
          {isAdmin ? (
            <>
              <p style={{ margin: "0 0 0.5rem", fontWeight: "bold" }}>まだ試験コンテンツが登録されていません</p>
              <p style={{ margin: 0, fontSize: "0.9rem" }}>
                本番環境ではサーバー側スクレイピングは無効です。<br />
                管理者は <code>docs/HowToUse.md</code> の手順に従い、ローカル環境から本番 Cosmos へコンテンツを投入してください。
              </p>
            </>
          ) : (
            <p style={{ margin: 0 }}>まだ学習コンテンツが公開されていません。管理者による投入をお待ちください。</p>
          )}
        </div>
      )}

      <div style={s.grid}>
        {displayExams.map((exam) => {
          const meta = EXAM_META[exam.exam_id] ?? {
            color: colorForExam(exam.exam_id),
            desc: "",
          };
          return (
            <div
              key={exam.exam_id}
              style={s.card(meta.color)}
              onClick={() => navigate(`/exam/${exam.exam_id}`)}
              onMouseEnter={(e) =>
                (e.currentTarget.style.boxShadow = "0 4px 12px rgba(0,0,0,0.15)")
              }
              onMouseLeave={(e) => (e.currentTarget.style.boxShadow = "none")}
            >
              <div style={s.examId(meta.color)}>{exam.exam_name}</div>
              <p style={s.desc}>{meta.desc}</p>
              <span style={s.count}>
                {exam.path_count > 0 ? `${exam.path_count} ラーニングパス` : "ラーニングパスなし"}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
