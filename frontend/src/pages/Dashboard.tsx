import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { api, LearningPath, Unit } from "../api/client";

const s = {
  page: { maxWidth: 1100, margin: "0 auto", padding: "1.5rem", fontFamily: "sans-serif" } as const,
  form: { display: "flex", gap: "0.5rem", marginBottom: "1rem" } as const,
  input: { flex: 1, padding: "0.5rem 0.75rem", fontSize: "0.9rem", border: "1px solid #ccc", borderRadius: 4 } as const,
  btn: (color = "#0078d4") => ({ padding: "0.5rem 1rem", background: color, color: "#fff", border: "none", borderRadius: 4, cursor: "pointer", fontSize: "0.9rem" }) as const,
  card: { border: "1px solid #e1e4e8", borderRadius: 6, marginBottom: "0.75rem", overflow: "hidden" } as const,
  cardHeader: { background: "#f6f8fa", padding: "0.6rem 1rem", cursor: "pointer", display: "flex", justifyContent: "space-between", alignItems: "center" } as const,
  unitRow: (done: boolean) => ({ display: "flex", alignItems: "center", padding: "0.4rem 1rem 0.4rem 1.5rem", borderTop: "1px solid #eee", background: done ? "#f0fff4" : "#fff", gap: "0.5rem", cursor: "pointer" }) as const,
  badge: (color: string) => ({ fontSize: "0.7rem", padding: "2px 6px", borderRadius: 10, background: color, color: "#fff", whiteSpace: "nowrap" as const }),
  status: (ok: boolean) => ({ padding: "0.75rem", borderRadius: 4, background: ok ? "#d4edda" : "#f8d7da", marginBottom: "1rem" }),
};

export default function Dashboard() {
  const navigate = useNavigate();
  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState<{ text: string; ok: boolean } | null>(null);
  const [paths, setPaths] = useState<LearningPath[]>([]);
  const [openModule, setOpenModule] = useState<string | null>(null);
  const [unitMap, setUnitMap] = useState<Record<string, Unit[]>>({});

  useEffect(() => { loadPaths(); }, []);

  async function loadPaths() {
    try {
      const res = await fetch("/api/learning-paths");
      if (res.ok) setPaths(await res.json());
    } catch { /* 初回は空 */ }
  }

  async function handleScrape(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true); setMsg(null);
    try {
      const res = await api.scrapeUrl(url.trim());
      setMsg({ text: `スクレイピング完了！ ラーニングパスID: ${res.learning_path_id}`, ok: true });
      setUrl("");
      await loadPaths();
    } catch (err) {
      setMsg({ text: `エラー: ${err instanceof Error ? err.message : String(err)}`, ok: false });
    } finally { setLoading(false); }
  }

  async function toggleModule(moduleId: string) {
    if (openModule === moduleId) { setOpenModule(null); return; }
    setOpenModule(moduleId);
    if (!unitMap[moduleId]) {
      const units = await api.getModuleUnits(moduleId);
      setUnitMap(prev => ({ ...prev, [moduleId]: units }));
    }
  }

  return (
    <div style={s.page}>
      <h2 style={{ marginBottom: "0.5rem" }}>ラーニングパスを追加</h2>
      <form onSubmit={handleScrape} style={s.form}>
        <input
          style={s.input} type="url" value={url}
          onChange={e => setUrl(e.target.value)}
          placeholder="https://learn.microsoft.com/ja-jp/training/paths/..."
          required
        />
        <button type="submit" style={s.btn()} disabled={loading}>
          {loading ? "スクレイピング中..." : "スクレイピング開始"}
        </button>
      </form>

      {msg && <p style={s.status(msg.ok)}>{msg.text}</p>}

      {paths.map(path => (
        <div key={path.id}>
          <h3 style={{ margin: "1.5rem 0 0.5rem", borderBottom: "2px solid #0078d4", paddingBottom: "0.3rem" }}>
            {path.title}
          </h3>
          {(path.modules ?? []).map(mod => (
            <div key={mod.id} style={s.card}>
              <div style={s.cardHeader} onClick={() => toggleModule(mod.id)}>
                <span style={{ fontWeight: 500 }}>{mod.title}</span>
                <span style={{ color: "#666", fontSize: "0.85rem" }}>
                  {mod.unit_count} ユニット　{openModule === mod.id ? "▲" : "▼"}
                </span>
              </div>
              {openModule === mod.id && (
                <div>
                  {(unitMap[mod.id] ?? []).length === 0
                    ? <p style={{ padding: "0.5rem 1rem", color: "#888" }}>読み込み中...</p>
                    : (unitMap[mod.id] ?? []).map(unit => (
                      <div key={unit.id} style={s.unitRow(!!unit.summary_ja)}
                        onClick={() => navigate(`/unit/${unit.id}`)}>
                        <span style={{ flex: 1, fontSize: "0.9rem" }}>{unit.title}</span>
                        {unit.summary_ja
                          ? <span style={s.badge("#28a745")}>要約済</span>
                          : <span style={s.badge("#6c757d")}>未要約</span>}
                        <span style={s.btn("#0078d4")}>学習→</span>
                      </div>
                    ))
                  }
                </div>
              )}
            </div>
          ))}
        </div>
      ))}

      {paths.length === 0 && !loading && (
        <p style={{ color: "#888", marginTop: "2rem" }}>
          上のフォームにMicrosoft LearnのURLを入力してスクレイピングを開始してください。
        </p>
      )}
    </div>
  );
}
