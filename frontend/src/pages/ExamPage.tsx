import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { api, LearningPath } from "../api/client";

const EXAM_NAMES: Record<string, string> = {
  "az-500": "AZ-500",
  "sc-300": "SC-300",
  "sc-100": "SC-100",
};

const s = {
  page: { maxWidth: 900, margin: "0 auto", padding: "1.5rem", fontFamily: "sans-serif" } as const,
  form: { display: "flex", gap: "0.5rem", marginBottom: "1rem" } as const,
  input: { flex: 1, padding: "0.5rem 0.75rem", fontSize: "0.9rem", border: "1px solid #ccc", borderRadius: 4 } as const,
  btn: (color = "#0078d4") => ({ padding: "0.5rem 1rem", background: color, color: "#fff", border: "none", borderRadius: 4, cursor: "pointer", fontSize: "0.9rem" } as const),
  card: { border: "1px solid #e1e4e8", borderRadius: 6, padding: "1rem 1.25rem", marginBottom: "0.75rem", display: "flex", justifyContent: "space-between", alignItems: "center", cursor: "pointer", background: "#fff" } as const,
  status: (ok: boolean) => ({ padding: "0.75rem", borderRadius: 4, background: ok ? "#d4edda" : "#f8d7da", marginBottom: "1rem" } as const),
  back: { background: "none", border: "none", color: "#0078d4", cursor: "pointer", fontSize: "0.9rem", padding: 0, marginBottom: "1rem" } as const,
};

export default function ExamPage() {
  const { examId = "" } = useParams<{ examId: string }>();
  const navigate = useNavigate();
  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState<{ text: string; ok: boolean } | null>(null);
  const [paths, setPaths] = useState<LearningPath[]>([]);

  const examName = EXAM_NAMES[examId] ?? examId.toUpperCase();

  useEffect(() => {
    loadPaths();
  }, [examId]);

  async function loadPaths() {
    try {
      const res = await api.listLearningPaths(examId);
      setPaths(res);
    } catch { /* ignore */ }
  }

  async function handleScrape(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setMsg(null);
    try {
      const res = await api.scrapeUrl(url.trim(), examId, examName);
      const titles = res.paths.map(p => p.title).filter(Boolean).join("、");
      setMsg({
        text: `スクレイピング完了！ ${res.paths.length} 件のラーニングパスを取得${titles ? `：${titles}` : ""}`,
        ok: true,
      });
      setUrl("");
      await loadPaths();
    } catch (err) {
      setMsg({ text: `エラー: ${err instanceof Error ? err.message : String(err)}`, ok: false });
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={s.page}>
      <button style={s.back} onClick={() => navigate("/")}>← 試験一覧に戻る</button>

      <h2 style={{ marginBottom: "0.25rem" }}>{examName}</h2>
      <p style={{ color: "#666", marginTop: 0, marginBottom: "1.25rem" }}>ラーニングパスを追加または選択してください</p>

      <form onSubmit={handleScrape} style={s.form}>
        <input
          style={s.input}
          type="url"
          value={url}
          onChange={e => setUrl(e.target.value)}
          placeholder="コース or ラーニングパス URL（/training/courses/... または /training/paths/...）"
          required
        />
        <button type="submit" style={s.btn()} disabled={loading}>
          {loading ? "取得中..." : "追加"}
        </button>
      </form>
      <p style={{ fontSize: "0.8rem", color: "#888", margin: "-0.5rem 0 1rem" }}>
        例：<code>https://learn.microsoft.com/ja-jp/training/courses/az-500t00</code>（コースURLは配下のラーニングパスを一括取得）
      </p>

      {msg && <p style={s.status(msg.ok)}>{msg.text}</p>}

      {paths.length === 0 && !loading ? (
        <p style={{ color: "#888" }}>まだラーニングパスがありません。URLを入力して追加してください。</p>
      ) : (
        paths.map(path => (
          <div
            key={path.id}
            style={s.card}
            onClick={() => navigate(`/path/${path.id}`)}
            onMouseEnter={e => (e.currentTarget.style.background = "#f6f8fa")}
            onMouseLeave={e => (e.currentTarget.style.background = "#fff")}
          >
            <div>
              <div style={{ fontWeight: 500 }}>{path.title}</div>
              <div style={{ fontSize: "0.8rem", color: "#888", marginTop: "0.2rem" }}>
                {(path.modules ?? []).length} モジュール
              </div>
            </div>
            <span style={{ color: "#0078d4", fontSize: "0.9rem" }}>開く →</span>
          </div>
        ))
      )}
    </div>
  );
}
